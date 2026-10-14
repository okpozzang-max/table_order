from __future__ import annotations

import json
import time
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from scripts.seed import run_seed
from tests.conftest import FakeClock
from tests.live import Live, LiveServer, SseReader, wait_until


def parse(frame: str) -> tuple[str, dict]:
    lines = frame.split("\n")
    assert lines[0].startswith("event: ") and lines[1].startswith("data: "), frame
    data = json.loads(lines[1][len("data: "):])
    assert lines[0] == f"event: {data['type']}"
    return data["type"], data


class TestAccess:
    def test_requires_admin_token(self, client: TestClient, table_headers: dict[str, str]) -> None:  # US-E9
        res = client.get("/api/admin/events")
        assert res.status_code == 401 and res.json()["code"] == "UNAUTHORIZED"
        assert client.get("/api/admin/events", headers=table_headers).status_code == 401

    def test_rejected_without_opening_stream_live(self, live: Live) -> None:
        reader = SseReader(live.base_url, None)
        assert reader.status == 401
        reader.ended.wait(3)
        assert json.loads(reader.body)["code"] == "UNAUTHORIZED"
        assert live.container.broker.subscriber_count == 0
        reader.close()


class TestStream:
    def test_headers_and_connected_comment(self, live: Live) -> None:  # US-E6
        reader = SseReader(live.base_url, live.admin_token())
        try:
            assert reader.status == 200
            assert reader.headers["content-type"].startswith("text/event-stream")
            assert reader.headers["cache-control"] == "no-cache"
            assert reader.headers["x-accel-buffering"] == "no"
            assert reader.frame() == ": connected"
            assert wait_until(lambda: live.container.broker.subscriber_count == 1)
        finally:
            reader.close()

    def test_new_order_arrives_within_two_seconds(self, live: Live) -> None:  # US-A2.2
        reader = SseReader(live.base_url, live.admin_token())
        try:
            assert reader.frame() == ": connected"
            table = live.table_token(1)
            started = time.perf_counter()
            res = live.order(table)
            assert res.status_code == 201
            frame = reader.event(timeout=2.0)
            elapsed = time.perf_counter() - started
            assert frame is not None, "2초 안에 이벤트를 받지 못했어요"
            assert elapsed < 2.0
            kind, data = parse(frame)
            assert kind == "order_created"
            assert data == {"type": "order_created", "tableId": res.json()["tableId"], "payload": {"orderId": res.json()["id"]}}
        finally:
            reader.close()

    def test_full_lifecycle_events_in_order(self, live: Live) -> None:
        admin = live.admin_token()
        auth = {"Authorization": f"Bearer {admin}"}
        reader = SseReader(live.base_url, admin)
        try:
            reader.frame()
            order = live.order(live.table_token(1)).json()
            oid, tid = order["id"], order["tableId"]
            live.http.patch(f"/api/admin/orders/{oid}/status", json={"status": "PREPARING"}, headers=auth)
            live.http.delete(f"/api/admin/orders/{oid}", headers=auth)
            second = live.order(live.table_token(1)).json()
            live.http.post(f"/api/admin/tables/{tid}/end-session", headers=auth)
            menu = live.http.get("/api/admin/menus", headers=auth).json()[0]["menus"][0]
            live.http.put(
                f"/api/admin/menus/{menu['id']}",
                json={"name": menu["name"], "price": menu["price"], "description": menu["description"], "category": menu["category"], "imageUrl": None},
                headers=auth,
            )
            got = [parse(reader.event(timeout=3.0) or "") for _ in range(6)]
        finally:
            reader.close()
        assert [(t, d["tableId"], d["payload"]) for t, d in got] == [
            ("order_created", tid, {"orderId": oid}),
            ("order_status_changed", tid, {"orderId": oid, "status": "PREPARING"}),
            ("order_deleted", tid, {"orderId": oid}),
            ("order_created", tid, {"orderId": second["id"]}),
            ("session_ended", tid, {"archivedOrderCount": 1}),
            ("menu_changed", None, {}),
        ]

    def test_failed_requests_publish_nothing(self, live: Live) -> None:
        reader = SseReader(live.base_url, live.admin_token())
        try:
            reader.frame()
            assert live.order(live.table_token(1), total=1).status_code == 409
            assert reader.event(timeout=0.5) is None
        finally:
            reader.close()

    def test_every_subscriber_gets_every_event(self, live: Live) -> None:
        admin = live.admin_token()
        readers = [SseReader(live.base_url, admin) for _ in range(3)]
        try:
            for r in readers:
                assert r.frame() == ": connected"
            assert wait_until(lambda: live.container.broker.subscriber_count == 3)
            oid = live.order(live.table_token(1)).json()["id"]
            for r in readers:
                kind, data = parse(r.event(timeout=2.0) or "")
                assert kind == "order_created" and data["payload"] == {"orderId": oid}
        finally:
            for r in readers:
                r.close()

    def test_keep_alive_comments(self, live: Live) -> None:  # US-E6
        reader = SseReader(live.base_url, live.admin_token())
        try:
            assert reader.frame() == ": connected"
            assert reader.frame(timeout=3.0) == ": keep-alive"
            assert reader.frame(timeout=3.0) == ": keep-alive"
        finally:
            reader.close()

    def test_disconnect_releases_subscription(self, live: Live) -> None:
        reader = SseReader(live.base_url, live.admin_token())
        reader.frame()
        assert wait_until(lambda: live.container.broker.subscriber_count == 1)
        reader.close()
        assert wait_until(lambda: live.container.broker.subscriber_count == 0, timeout=5.0)

    def test_stream_ends_when_token_expires(self, live: Live, clock: FakeClock) -> None:  # G20
        reader = SseReader(live.base_url, live.admin_token())
        try:
            assert reader.frame() == ": connected"
            clock.advance(16 * 3600 + 60)
            assert reader.ended.wait(5.0), "토큰 만료 후에도 스트림이 닫히지 않았어요"
            assert wait_until(lambda: live.container.broker.subscriber_count == 0)
        finally:
            reader.close()

    def test_stream_ends_when_broker_closes_all(self, live: Live) -> None:
        reader = SseReader(live.base_url, live.admin_token())
        try:
            reader.frame()
            assert wait_until(lambda: live.container.broker.subscriber_count == 1)
            live.container.broker.close_all()
            assert reader.ended.wait(5.0)
        finally:
            reader.close()

    def test_server_shutdown_with_open_stream_does_not_hang(self, settings: Settings, clock: FakeClock) -> None:
        application = create_app(settings, clock)
        run_seed(application.state.container.db, bcrypt_rounds=4, now=clock())
        server = LiveServer(application).start()
        live = Live(server, application.state.container)
        reader = SseReader(server.base_url, live.admin_token())
        reader.frame()
        started = time.perf_counter()
        server.stop()  # timeout_graceful_shutdown=2 로 열린 스트림이 있어도 끝나야 한다
        assert time.perf_counter() - started < 8
        assert reader.ended.wait(5.0)
        reader.close()
