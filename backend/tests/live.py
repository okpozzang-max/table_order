"""실제 uvicorn 서버를 스레드로 띄우는 테스트 도구 (SSE/통합 시나리오용).

TestClient는 끝나지 않는 스트림을 다루기 어렵기 때문에, 실제 소켓과 httpx 스트리밍으로 확인한다.
"""

from __future__ import annotations

import queue
import socket
import threading
import time
from collections.abc import Callable

import uuid

import httpx
import uvicorn
from fastapi import FastAPI

from app.deps import AppContainer
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, STORE_ID, TABLE_PASSWORD


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LiveServer:
    def __init__(self, app: FastAPI) -> None:
        self.port = _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="warning", lifespan="on", timeout_graceful_shutdown=2
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> LiveServer:
        self._thread.start()
        deadline = time.time() + 10
        while not self._server.started:
            if time.time() > deadline or not self._thread.is_alive():
                raise RuntimeError("테스트 서버가 시작되지 않았어요")
            time.sleep(0.02)
        return self

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)

    def __enter__(self) -> LiveServer:
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.stop()


class SseReader:
    """SSE 스트림을 별도 스레드에서 읽어 프레임 단위로 꺼내 쓰게 한다."""

    def __init__(self, base_url: str, token: str | None, path: str = "/api/admin/events") -> None:
        self._url = base_url + path
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._lines: queue.Queue[str] = queue.Queue()
        self._client = httpx.Client(timeout=httpx.Timeout(10.0, read=None))
        self._ready = threading.Event()
        self.ended = threading.Event()
        self.status: int | None = None
        self.headers: httpx.Headers | None = None
        self.body = b""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("SSE 응답 헤더를 받지 못했어요")

    def _run(self) -> None:
        try:
            with self._client.stream("GET", self._url, headers=self._headers) as response:
                self.status = response.status_code
                self.headers = response.headers
                self._ready.set()
                if response.status_code != 200:
                    self.body = response.read()
                    return
                for line in response.iter_lines():
                    self._lines.put(line)
        except Exception:  # noqa: BLE001  (close()로 닫힌 경우 포함)
            pass
        finally:
            self._ready.set()
            self.ended.set()

    def frame(self, timeout: float = 3.0) -> str | None:
        """다음 프레임(빈 줄까지)을 문자열로. 시간 안에 오지 않으면 None."""
        deadline = time.time() + timeout
        lines: list[str] = []
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                line = self._lines.get(timeout=min(remaining, 0.1))
            except queue.Empty:
                if self.ended.is_set() and self._lines.empty():
                    return None
                continue
            if line == "":
                if lines:
                    return "\n".join(lines)
                continue
            lines.append(line)

    def event(self, timeout: float = 3.0, skip_comments: bool = True) -> str | None:
        """주석(`:`)을 건너뛰고 다음 이벤트 프레임을 돌려준다."""
        deadline = time.time() + timeout
        while True:
            frame = self.frame(max(0.0, deadline - time.time()))
            if frame is None:
                return None
            if skip_comments and frame.startswith(":"):
                continue
            return frame

    def close(self) -> None:
        self._client.close()
        self._thread.join(timeout=5)


class Live:
    def __init__(self, server: LiveServer, container: AppContainer) -> None:
        self.server = server
        self.container = container
        self.http = httpx.Client(base_url=server.base_url, timeout=10)

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def admin_token(self) -> str:
        res = self.http.post("/api/admin/auth/login", json={"storeId": STORE_ID, "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        assert res.status_code == 200, res.text
        return res.json()["accessToken"]

    def table_token(self, number: int = 1) -> str:
        res = self.http.post("/api/customer/auth/login", json={"storeId": STORE_ID, "tableNumber": number, "password": TABLE_PASSWORD})
        assert res.status_code == 200, res.text
        return res.json()["accessToken"]

    def order(self, token: str, items: list[tuple[int, int]] | None = None, total: int | None = None) -> httpx.Response:
        items = items or [(1, 1)]
        prices = {1: 9000, 2: 8500, 6: 1000}
        return self.http.post(
            "/api/customer/orders",
            json={
                "clientOrderId": str(uuid.uuid4()),
                "items": [{"menuId": m, "quantity": q} for m, q in items],
                "clientTotal": sum(prices[m] * q for m, q in items) if total is None else total,
            },
            headers={"Authorization": f"Bearer {token}"},
        )


def wait_until(condition: Callable[[], bool], timeout: float = 3.0, interval: float = 0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()
