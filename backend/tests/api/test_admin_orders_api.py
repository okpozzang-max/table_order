from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import RecordingPublisher, bearer, login_table

ORDERS = "/api/customer/orders"
DASH = "/api/admin/dashboard"


def place(client: TestClient, headers: dict[str, str], items: list[tuple[int, int]] | None = None) -> dict:
    items = items or [(1, 1)]
    prices = {1: 9000, 2: 8500, 6: 1000, 8: 2000}
    res = client.post(
        ORDERS,
        json={
            "clientOrderId": str(uuid.uuid4()),
            "items": [{"menuId": m, "quantity": q} for m, q in items],
            "clientTotal": sum(prices[m] * q for m, q in items),
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


class TestDashboard:
    def test_all_tables_in_number_order_with_empty_summaries(self, client: TestClient, admin_headers: dict[str, str]) -> None:  # US-A2.1
        res = client.get(DASH, headers=admin_headers)
        assert res.status_code == 200
        board = res.json()
        assert [t["tableNumber"] for t in board] == [1, 2, 3, 4, 5]
        assert set(board[0]) == {"tableId", "tableNumber", "sessionActive", "totalAmount", "orderCount", "orders"}
        assert all(t["sessionActive"] is False and t["orders"] == [] and t["totalAmount"] == 0 for t in board)

    def test_preview_latest_three_and_totals(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        ids = [place(client, table_headers, [(6, i + 1)])["id"] for i in range(5)]
        t1 = client.get(DASH, headers=admin_headers).json()[0]
        assert [o["id"] for o in t1["orders"]] == ids[::-1][:3]
        assert (t1["orderCount"], t1["totalAmount"], t1["sessionActive"]) == (5, 15000, True)

    def test_table_filter_returns_all_current_session_orders(  # US-A2.5
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]
    ) -> None:
        ids = [place(client, table_headers)["id"] for _ in range(5)]
        place(client, bearer(login_table(client, 2)))
        res = client.get(DASH, params={"table": 1}, headers=admin_headers).json()
        assert len(res) == 1 and res[0]["tableNumber"] == 1
        assert [o["id"] for o in res[0]["orders"]] == ids[::-1]

    def test_unknown_table_404_and_bad_param_422(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.get(DASH, params={"table": 99}, headers=admin_headers).status_code == 404
        for value in ("0", "-1", "abc"):
            res = client.get(DASH, params={"table": value}, headers=admin_headers)
            assert res.status_code == 422 and "table" in res.json()["fields"]

    def test_requires_admin_token(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.get(DASH).status_code == 401
        assert client.get(DASH, headers=table_headers).status_code == 401


class TestOrderDetail:
    def test_get_order(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:  # US-A2.3
        order = place(client, table_headers, [(1, 2), (6, 1)])
        res = client.get(f"/api/admin/orders/{order['id']}", headers=admin_headers)
        assert res.status_code == 200 and res.json() == order

    def test_not_found_and_bad_id(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.get("/api/admin/orders/999", headers=admin_headers).status_code == 404
        res = client.get("/api/admin/orders/abc", headers=admin_headers)
        assert res.status_code == 422 and "orderId" in res.json()["fields"]

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.get("/api/admin/orders/1").status_code == 401
        assert client.get("/api/admin/orders/1", headers=table_headers).status_code == 401


class TestChangeStatus:
    def _url(self, oid: int) -> str:
        return f"/api/admin/orders/{oid}/status"

    def test_sequential_transitions(  # US-A2.4
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        oid = place(client, table_headers)["id"]
        publisher.events.clear()
        r1 = client.patch(self._url(oid), json={"status": "PREPARING"}, headers=admin_headers)
        r2 = client.patch(self._url(oid), json={"status": "COMPLETED"}, headers=admin_headers)
        assert (r1.status_code, r1.json()["status"]) == (200, "PREPARING")
        assert (r2.status_code, r2.json()["status"]) == (200, "COMPLETED")
        assert [(e.type, e.payload) for e in publisher.events] == [
            ("order_status_changed", {"orderId": oid, "status": "PREPARING"}),
            ("order_status_changed", {"orderId": oid, "status": "COMPLETED"}),
        ]

    def test_invalid_transitions_409(  # US-E5
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        oid = place(client, table_headers)["id"]
        publisher.events.clear()
        for status in ("COMPLETED", "PENDING"):
            res = client.patch(self._url(oid), json={"status": status}, headers=admin_headers)
            assert res.status_code == 409 and res.json()["code"] == "INVALID_TRANSITION"
        client.patch(self._url(oid), json={"status": "PREPARING"}, headers=admin_headers)
        client.patch(self._url(oid), json={"status": "COMPLETED"}, headers=admin_headers)
        for status in ("PENDING", "PREPARING", "COMPLETED"):
            assert client.patch(self._url(oid), json={"status": status}, headers=admin_headers).status_code == 409
        assert len(publisher.events) == 2

    def test_unknown_order_404_even_for_invalid_transition(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.patch(self._url(999), json={"status": "COMPLETED"}, headers=admin_headers).status_code == 404

    def test_invalid_status_value_422(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        oid = place(client, table_headers)["id"]
        for payload in ({"status": "DONE"}, {"status": "pending"}, {}, {"status": 3}):
            res = client.patch(self._url(oid), json=payload, headers=admin_headers)
            assert res.status_code == 422 and "status" in res.json()["fields"]

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.patch(self._url(1), json={"status": "PREPARING"}).status_code == 401
        assert client.patch(self._url(1), json={"status": "PREPARING"}, headers=table_headers).status_code == 401


class TestDeleteOrder:
    def test_delete_returns_recalculated_summary(  # US-A3.2
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        a = place(client, table_headers, [(1, 1)])
        b = place(client, table_headers, [(2, 1)])
        publisher.events.clear()
        res = client.delete(f"/api/admin/orders/{a['id']}", headers=admin_headers)
        assert res.status_code == 200
        summary = res.json()
        assert (summary["orderCount"], summary["totalAmount"], summary["tableNumber"]) == (1, 8500, 1)
        assert [o["id"] for o in summary["orders"]] == [b["id"]]
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [("order_deleted", a["tableId"], {"orderId": a["id"]})]
        assert client.get(f"/api/admin/orders/{a['id']}", headers=admin_headers).status_code == 404

    def test_delete_unknown_404_and_repeat_404(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        assert client.delete("/api/admin/orders/999", headers=admin_headers).status_code == 404
        oid = place(client, table_headers)["id"]
        assert client.delete(f"/api/admin/orders/{oid}", headers=admin_headers).status_code == 200
        assert client.delete(f"/api/admin/orders/{oid}", headers=admin_headers).status_code == 404

    def test_last_order_deleted_leaves_empty_active_summary(self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]) -> None:
        oid = place(client, table_headers)["id"]
        summary = client.delete(f"/api/admin/orders/{oid}", headers=admin_headers).json()
        assert (summary["sessionActive"], summary["orderCount"], summary["totalAmount"], summary["orders"]) == (True, 0, 0, [])

    def test_requires_admin(self, client: TestClient, table_headers: dict[str, str]) -> None:
        assert client.delete("/api/admin/orders/1").status_code == 401
        assert client.delete("/api/admin/orders/1", headers=table_headers).status_code == 401
