"""EventBroker: 관리자 SSE 구독자에게 서버 이벤트를 전달한다.

- `publish()`는 동기 서비스(스레드풀)를 포함해 어느 스레드에서든 호출할 수 있고 절대 블로킹하지 않는다.
- 구독은 호출한 이벤트 루프에 묶인다(구독별 asyncio.Queue). 발행은 구독별로 `call_soon_threadsafe`로 넘긴다.
- 큐가 가득 찬 느린 구독자는 대기 중이던 이벤트를 버리고 종료 신호를 받는다(클라이언트는 재연결 후 재조회).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable
from datetime import datetime

from .events_port import ServerEvent

logger = logging.getLogger("app.events")

CLOSE_OVERFLOW = "overflow"
CLOSE_SHUTDOWN = "shutdown"


class _Close:
    """큐에 넣는 종료 신호."""


_CLOSE = _Close()


class Subscription:
    def __init__(self, broker: EventBroker, loop: asyncio.AbstractEventLoop, maxsize: int) -> None:
        self._broker = broker
        self.loop = loop
        self.queue: asyncio.Queue[ServerEvent | _Close] = asyncio.Queue(maxsize=maxsize)
        self.close_reason: str | None = None

    # 아래 두 메서드는 구독의 이벤트 루프 스레드에서만 실행된다.
    def _deliver(self, event: ServerEvent) -> None:
        if self.close_reason is not None:
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("느린 구독자의 연결을 끊어요 (큐가 가득 참)")
            self._close(CLOSE_OVERFLOW)
            self._broker.unsubscribe(self)

    def _close(self, reason: str) -> None:
        if self.close_reason is not None:
            return
        self.close_reason = reason
        # 밀린 이벤트는 의미가 없다 (클라이언트가 재연결 후 다시 조회). 종료 신호가 들어갈 자리를 만든다.
        while True:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.queue.put_nowait(_CLOSE)


class EventBroker:
    def __init__(self, queue_size: int = 100) -> None:
        self._queue_size = queue_size
        self._lock = threading.Lock()
        self._subs: list[Subscription] = []

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    def subscribe(self) -> Subscription:
        """이벤트 루프 안에서 호출한다 (구독이 그 루프에 묶인다)."""
        sub = Subscription(self, asyncio.get_running_loop(), self._queue_size)
        with self._lock:
            self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)

    def publish(self, event: ServerEvent) -> None:
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub._deliver, event)
            except RuntimeError:  # 루프가 이미 닫힘 (연결이 사라진 구독)
                self.unsubscribe(sub)

    def close_all(self) -> None:
        """서버 종료 시 모든 구독에 종료 신호를 보낸다."""
        with self._lock:
            subs = list(self._subs)
            self._subs.clear()
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub._close, CLOSE_SHUTDOWN)
            except RuntimeError:
                pass


class CompositePublisher:
    """여러 발행기에 차례로 전달한다 (브로커 + 테스트용 기록 발행기 등). 한 쪽의 실패가 다른 쪽을 막지 않는다."""

    def __init__(self, *publishers: object) -> None:
        self._publishers = list(publishers)

    def publish(self, event: ServerEvent) -> None:
        for publisher in self._publishers:
            try:
                publisher.publish(event)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                logger.exception("이벤트 발행기 하나가 실패했어요: %s", event.type)


def format_sse(event: ServerEvent) -> str:
    """`event: <type>\\ndata: <ServerEvent JSON 한 줄>\\n\\n`"""
    data = json.dumps(
        {"type": event.type, "tableId": event.table_id, "payload": event.payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event.type}\ndata: {data}\n\n"


async def stream_events(
    broker: EventBroker,
    *,
    keepalive_seconds: float,
    expires_at: int | None = None,
    now: Callable[[], datetime],
    sub: Subscription | None = None,
) -> AsyncIterator[str]:
    """SSE 프레임을 생성한다.

    종료 조건: 종료 신호(overflow/서버 종료), 토큰 만료 시각 도달, 호출자의 취소(클라이언트 연결 끊김).
    어떤 경우든 마지막에 구독을 해제한다. `sub`을 넘기면 그 구독을 사용한다(스트림을 열기 전에 구독을 확보할 때).
    """
    sub = sub or broker.subscribe()
    try:
        yield ": connected\n\n"
        while True:
            timeout = float(keepalive_seconds)
            if expires_at is not None:
                remaining = expires_at - now().timestamp()
                if remaining <= 0:
                    return
                timeout = min(timeout, remaining)
            try:
                item = await asyncio.wait_for(sub.queue.get(), timeout)
            except asyncio.TimeoutError:
                if expires_at is not None and now().timestamp() >= expires_at:
                    return
                yield ": keep-alive\n\n"
                continue
            if isinstance(item, _Close):
                return
            yield format_sse(item)
    finally:
        broker.unsubscribe(sub)
