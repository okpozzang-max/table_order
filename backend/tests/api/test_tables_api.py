from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from tests.api.test_admin_orders_api import place
from tests.conftest import STORE_ID, RecordingPublisher, bearer, login_table

TABLES = "/api/admin/tables"


def reg(client: TestClient, headers: dict[str, str], number: object = 6, password: object = "4321"):  # type: ignore[no-untyped-def]
    return client.post(TABLES, json={"tableNumber": number, "password": password}, headers=headers)


class TestRegisterAndList:
    def test_register_201_and_listed(self, client: TestClient, admin_headers: dict[str, str]) -> None:  # US-A3.1
        res = reg(client, admin_headers, 6)
        assert res.status_code == 201
        info = res.json()
        assert set(info) == {"id", "tableNumber", "sessionActive"} and info["tableNumber"] == 6 and info["sessionActive"] is False
        listing = client.get(TABLES, headers=admin_headers).json()
        assert [t["tableNumber"] for t in listing] == [1, 2, 3, 4, 5, 6]
        assert all(t["sessionActive"] is False for t in listing)

    def test_registered_table_logs_in_right_away_with_same_password(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        reg(client, admin_headers, 7, "9876")
        ok = client.post("/api/customer/auth/login", json={"storeId": STORE_ID, "tableNumber": 7, "password": "9876"})
        assert ok.status_code == 200 and ok.json()["tableNumber"] == 7
        bad = client.post("/api/customer/auth/login", json={"storeId": STORE_ID, "tableNumber": 7, "password": "1234"})
        assert bad.status_code == 401

    def test_duplicate_409(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        res = reg(client, admin_headers, 3)
        assert res.status_code == 409 and res.json()["code"] == "DUPLICATE_TABLE"

    def test_validation_422(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        for number in (0, 1000, -1):
            res = reg(client, admin_headers, number)
            assert res.status_code == 422 and res.json()["fields"] == {"tableNumber": "테이블 번호는 1~999 사이 숫자로 입력해주세요."}
        for password in ("123", "12345", "abcd", ""):
            res = reg(client, admin_headers, 8, password)
            assert res.status_code == 422 and res.json()["fields"] == {"password": "비밀번호는 숫자 4자리입니다."}
        res = reg(client, admin_headers, "x", 12)
        assert res.status_code == 422 and {"tableNumber", "password"} <= set(res.json()["fields"])

    def test_session_active_flag_follows_orders(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        place(client, table_headers)
        flags = {t["tableNumber"]: t["sessionActive"] for t in client.get(TABLES, headers=admin_headers).json()}
        assert flags == {1: True, 2: False, 3: False, 4: False, 5: False}

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        for headers in ({}, table_headers):
            assert client.get(TABLES, headers=headers).status_code == 401
            assert client.post(TABLES, json={"tableNumber": 6, "password": "1234"}, headers=headers).status_code == 401


class TestEndSession:
    def test_end_session_archives_and_resets_dashboard(  # US-A3.3
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        a = place(client, table_headers, [(1, 2)])
        b = place(client, table_headers, [(6, 1)])
        publisher.events.clear()
        res = client.post(f"{TABLES}/{a['tableId']}/end-session", headers=admin_headers)
        assert res.status_code == 200
        summary = res.json()
        assert set(summary) == {"tableId", "endedAt", "archivedOrderCount", "archivedTotalAmount"}
        assert (summary["archivedOrderCount"], summary["archivedTotalAmount"]) == (2, 19000)
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [("session_ended", a["tableId"], {"archivedOrderCount": 2})]

        board = client.get("/api/admin/dashboard", headers=admin_headers).json()[0]
        assert (board["sessionActive"], board["totalAmount"], board["orderCount"], board["orders"]) == (False, 0, 0, [])
        assert client.get(f"/api/admin/orders/{a['id']}", headers=admin_headers).status_code == 404
        history = client.get(f"{TABLES}/{a['tableId']}/history", headers=admin_headers).json()
        assert [h["orderId"] for h in history] == [b["id"], a["id"]]

    def test_second_call_409_and_never_used_table_409(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:  # US-E8
        o = place(client, table_headers)
        url = f"{TABLES}/{o['tableId']}/end-session"
        assert client.post(url, headers=admin_headers).status_code == 200
        res = client.post(url, headers=admin_headers)
        assert res.status_code == 409 and res.json()["code"] == "NO_ACTIVE_SESSION"
        assert client.post(f"{TABLES}/2/end-session", headers=admin_headers).status_code == 409

    def test_unknown_table_404_and_bad_id_422(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.post(f"{TABLES}/999/end-session", headers=admin_headers).status_code == 404
        res = client.post(f"{TABLES}/abc/end-session", headers=admin_headers)
        assert res.status_code == 422 and "tableId" in res.json()["fields"]

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.post(f"{TABLES}/1/end-session").status_code == 401
        assert client.post(f"{TABLES}/1/end-session", headers=table_headers).status_code == 401

    def test_new_order_after_end_starts_new_session(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        first = place(client, table_headers)
        client.post(f"{TABLES}/{first['tableId']}/end-session", headers=admin_headers)
        second = place(client, table_headers)
        assert second["sessionId"] != first["sessionId"]
        board = client.get("/api/admin/dashboard", headers=admin_headers).json()[0]
        assert (board["sessionActive"], board["orderCount"]) == (True, 1)


class TestHistory:
    def _end_at(self, client: TestClient, admin_headers: dict[str, str], headers: dict[str, str], clock, when: datetime) -> dict:  # type: ignore[no-untyped-def]
        clock.now = when
        order = place(client, headers)
        assert client.post(f"{TABLES}/{order['tableId']}/end-session", headers=admin_headers).status_code == 200
        return order

    def test_shape_and_filters(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], clock) -> None:  # type: ignore[no-untyped-def]
        # 한국 시간 기준: 10-14 23:59:59 KST (= 14:59:59Z) / 10-15 00:00:00 KST (= 15:00:00Z)
        early = self._end_at(client, admin_headers, table_headers, clock, datetime(2026, 10, 14, 14, 59, 59, tzinfo=timezone.utc))
        late = self._end_at(client, admin_headers, table_headers, clock, datetime(2026, 10, 14, 15, 0, 0, tzinfo=timezone.utc))
        url = f"{TABLES}/{early['tableId']}/history"

        everything = client.get(url, headers=admin_headers).json()
        assert [h["orderId"] for h in everything] == [late["id"], early["id"]]
        assert set(everything[0]) == {"orderId", "orderNumber", "tableNumber", "createdAt", "items", "totalAmount", "completedAt"}
        assert everything[0]["completedAt"] == "2026-10-14T15:00:00Z"
        assert everything[0]["items"] == late["items"]

        ids = lambda **p: [h["orderId"] for h in client.get(url, params=p, headers=admin_headers).json()]  # noqa: E731
        assert ids(**{"from": "2026-10-15"}) == [late["id"]]
        assert ids(to="2026-10-14") == [early["id"]]
        assert ids(**{"from": "2026-10-14", "to": "2026-10-14"}) == [early["id"]]
        assert ids(**{"from": "2026-10-14", "to": "2026-10-15"}) == [late["id"], early["id"]]
        assert ids(**{"from": "2026-10-16"}) == []

    def test_validation_and_not_found(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        url = f"{TABLES}/1/history"
        reversed_ = client.get(url, params={"from": "2026-10-15", "to": "2026-10-14"}, headers=admin_headers)
        assert reversed_.status_code == 422 and reversed_.json()["fields"] == {"from": "시작일이 종료일보다 늦을 수 없습니다."}
        for bad in ({"from": "2026-13-01"}, {"to": "yesterday"}, {"from": "20261014"}):
            res = client.get(url, params=bad, headers=admin_headers)
            assert res.status_code == 422, bad
            assert set(res.json()["fields"]) <= {"from", "to"} and res.json()["fields"]
        assert client.get(f"{TABLES}/999/history", headers=admin_headers).status_code == 404
        assert client.get(f"{TABLES}/1/history", headers=admin_headers).json() == []

    def test_validation_happens_before_not_found(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        res = client.get(f"{TABLES}/999/history", params={"from": "2026-10-15", "to": "2026-10-14"}, headers=admin_headers)
        assert res.status_code == 422

    def test_other_table_history_is_separate(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        o1 = place(client, table_headers)
        o2 = place(client, bearer(login_table(client, 2)))
        for o in (o1, o2):
            client.post(f"{TABLES}/{o['tableId']}/end-session", headers=admin_headers)
        h1 = client.get(f"{TABLES}/{o1['tableId']}/history", headers=admin_headers).json()
        assert [h["orderId"] for h in h1] == [o1["id"]] and h1[0]["tableNumber"] == 1

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.get(f"{TABLES}/1/history").status_code == 401
        assert client.get(f"{TABLES}/1/history", headers=table_headers).status_code == 401
