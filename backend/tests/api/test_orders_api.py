from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import RecordingPublisher, bearer, login_table

ORDERS = "/api/customer/orders"


def body(items: list[tuple[int, int]] | None = None, total: int | None = None, cid: str | None = None) -> dict[str, object]:
    items = items or [(1, 2)]  # 김치찌개 9000 x 2
    prices = {1: 9000, 2: 8500, 6: 1000}
    return {
        "clientOrderId": cid or str(uuid.uuid4()),
        "items": [{"menuId": m, "quantity": q} for m, q in items],
        "clientTotal": sum(prices[m] * q for m, q in items) if total is None else total,
    }


class TestCreateOrder:
    def test_created_201_with_contract_shape(self, client: TestClient, table_headers: dict[str, str]) -> None:  # US-C4.1, C4.2
        res = client.post(ORDERS, json=body([(1, 2), (6, 1)]), headers=table_headers)
        assert res.status_code == 201
        order = res.json()
        assert set(order) == {"id", "orderNumber", "tableId", "tableNumber", "sessionId", "createdAt", "status", "totalAmount", "items"}
        assert order["orderNumber"] == str(order["id"]).zfill(4)
        assert order["status"] == "PENDING" and order["totalAmount"] == 19000 and order["tableNumber"] == 1
        assert order["sessionId"].startswith("sess_")
        assert order["createdAt"].endswith("Z")
        assert order["items"] == [
            {"menuId": 1, "menuName": "김치찌개", "quantity": 2, "unitPrice": 9000},
            {"menuId": 6, "menuName": "공기밥", "quantity": 1, "unitPrice": 1000},
        ]

    def test_replay_returns_200_with_same_order(  # 멱등성
        self, client: TestClient, table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        payload = body()
        first = client.post(ORDERS, json=payload, headers=table_headers)
        publisher.events.clear()
        again = client.post(ORDERS, json=payload, headers=table_headers)
        assert (first.status_code, again.status_code) == (201, 200)
        assert again.json() == first.json()
        assert publisher.events == []
        assert len(client.get(ORDERS, headers=table_headers).json()["items"]) == 1

    def test_uppercase_client_order_id_is_same_key(self, client: TestClient, table_headers: dict[str, str]) -> None:
        cid = str(uuid.uuid4())
        assert client.post(ORDERS, json=body(cid=cid), headers=table_headers).status_code == 201
        assert client.post(ORDERS, json=body(cid=cid.upper()), headers=table_headers).status_code == 200

    def test_price_changed_409_with_current_prices(self, client: TestClient, table_headers: dict[str, str]) -> None:  # US-C4.1
        res = client.post(ORDERS, json=body([(1, 1), (6, 1)], total=1), headers=table_headers)
        assert res.status_code == 409
        err = res.json()
        assert err["code"] == "PRICE_CHANGED"
        assert err["details"]["currentPrices"] == [{"menuId": 1, "price": 9000}, {"menuId": 6, "price": 1000}]

    def test_unavailable_menu_409_lists_ids(  # US-E2
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]
    ) -> None:
        assert client.delete("/api/admin/menus/2", headers=admin_headers).status_code == 204
        res = client.post(ORDERS, json=body([(1, 1), (2, 1)], total=17500), headers=table_headers)
        assert res.status_code == 409
        assert res.json()["code"] == "MENU_UNAVAILABLE" and res.json()["details"] == {"menuIds": [2]}
        assert client.get(ORDERS, headers=table_headers).json()["items"] == []  # US-E1: 아무것도 저장되지 않음

    def test_nonexistent_menu_is_unavailable(self, client: TestClient, table_headers: dict[str, str]) -> None:
        payload = {"clientOrderId": str(uuid.uuid4()), "items": [{"menuId": 999, "quantity": 1}], "clientTotal": 100}
        res = client.post(ORDERS, json=payload, headers=table_headers)
        assert res.status_code == 409 and res.json()["details"] == {"menuIds": [999]}

    def test_price_update_then_old_price_order_rejected_new_price_accepted(  # 가격 변경 흐름
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]
    ) -> None:
        menu = client.get("/api/admin/menus", headers=admin_headers).json()[0]["menus"][0]
        update = {"name": menu["name"], "price": 10000, "description": menu["description"], "category": menu["category"], "imageUrl": None}
        assert client.put(f"/api/admin/menus/{menu['id']}", json=update, headers=admin_headers).status_code == 200
        stale = client.post(ORDERS, json=body([(1, 1)], total=9000), headers=table_headers)
        assert stale.status_code == 409 and stale.json()["details"]["currentPrices"] == [{"menuId": 1, "price": 10000}]
        fresh = client.post(ORDERS, json=body([(1, 1)], total=10000), headers=table_headers)
        assert fresh.status_code == 201 and fresh.json()["items"][0]["unitPrice"] == 10000

    def test_validation_errors_are_collected(self, client: TestClient, table_headers: dict[str, str]) -> None:
        res = client.post(ORDERS, json={"clientOrderId": "nope", "items": [], "clientTotal": -1}, headers=table_headers)
        assert res.status_code == 422
        assert set(res.json()["fields"]) == {"clientOrderId", "items", "clientTotal"}
        assert res.json()["code"] == "VALIDATION_ERROR"

    def test_quantity_limits(self, client: TestClient, table_headers: dict[str, str]) -> None:
        for qty in (0, 21):
            res = client.post(ORDERS, json=body([(6, qty)], total=1000 * qty), headers=table_headers)
            assert res.status_code == 422 and res.json()["fields"]["items"] == "수량은 1~20 사이로 입력해주세요."
        assert client.post(ORDERS, json=body([(6, 20)]), headers=table_headers).status_code == 201

    def test_duplicate_menu_lines_rejected(self, client: TestClient, table_headers: dict[str, str]) -> None:
        res = client.post(ORDERS, json=body([(1, 1), (1, 1)]), headers=table_headers)
        assert res.status_code == 422 and "items" in res.json()["fields"]

    def test_type_errors_map_to_fields(self, client: TestClient, table_headers: dict[str, str]) -> None:
        payload = {"clientOrderId": str(uuid.uuid4()), "items": [{"menuId": 1, "quantity": "2"}], "clientTotal": "x"}
        res = client.post(ORDERS, json=payload, headers=table_headers)
        assert res.status_code == 422 and {"items", "clientTotal"} <= set(res.json()["fields"])

    def test_missing_body_fields(self, client: TestClient, table_headers: dict[str, str]) -> None:
        res = client.post(ORDERS, json={}, headers=table_headers)
        assert res.status_code == 422 and {"clientOrderId", "items", "clientTotal"} <= set(res.json()["fields"])

    def test_order_events_published_after_success_only(
        self, client: TestClient, table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        publisher.events.clear()
        client.post(ORDERS, json=body(total=1), headers=table_headers)  # 409
        assert publisher.events == []
        order = client.post(ORDERS, json=body(), headers=table_headers).json()
        assert [(e.type, e.payload) for e in publisher.events] == [("order_created", {"orderId": order["id"]})]


class TestAuth:
    def test_missing_token_401(self, client: TestClient) -> None:  # US-E9
        for res in (client.post(ORDERS, json=body()), client.get(ORDERS)):
            assert res.status_code == 401 and res.json()["code"] == "UNAUTHORIZED"
            assert res.headers["www-authenticate"] == "Bearer"

    def test_admin_token_is_not_accepted(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.post(ORDERS, json=body(), headers=admin_headers).status_code == 401
        assert client.get(ORDERS, headers=admin_headers).status_code == 401

    def test_auth_is_checked_before_validation(self, client: TestClient) -> None:
        assert client.post(ORDERS, json={}).status_code == 401

    def test_expired_token_401(self, client: TestClient, table_headers: dict[str, str], clock) -> None:  # type: ignore[no-untyped-def]
        clock.advance(16 * 3600 + 1)
        assert client.get(ORDERS, headers=table_headers).status_code == 401


class TestListOrders:
    def test_empty_without_session(self, client: TestClient, table_headers: dict[str, str]) -> None:
        res = client.get(ORDERS, headers=table_headers)
        assert res.status_code == 200
        assert res.json() == {"items": [], "page": 0, "size": 10, "hasNext": False}

    def test_newest_first_with_paging(self, client: TestClient, table_headers: dict[str, str]) -> None:  # US-C5.1
        ids = [client.post(ORDERS, json=body(), headers=table_headers).json()["id"] for _ in range(12)]
        p0 = client.get(ORDERS, headers=table_headers).json()
        p1 = client.get(ORDERS, params={"page": 1}, headers=table_headers).json()
        assert [o["id"] for o in p0["items"]] == ids[::-1][:10] and p0["hasNext"] is True
        assert [o["id"] for o in p1["items"]] == ids[::-1][10:] and p1["hasNext"] is False
        small = client.get(ORDERS, params={"size": 5, "page": 2}, headers=table_headers).json()
        assert (small["page"], small["size"], len(small["items"]), small["hasNext"]) == (2, 5, 2, False)

    def test_only_own_table_and_current_session(self, client: TestClient, table_headers: dict[str, str], admin_headers: dict[str, str]) -> None:
        other = bearer(login_table(client, 2))
        mine = client.post(ORDERS, json=body(), headers=table_headers).json()
        client.post(ORDERS, json=body(), headers=other)
        assert [o["id"] for o in client.get(ORDERS, headers=table_headers).json()["items"]] == [mine["id"]]
        table_id = mine["tableId"]
        assert client.post(f"/api/admin/tables/{table_id}/end-session", headers=admin_headers).status_code == 200
        assert client.get(ORDERS, headers=table_headers).json()["items"] == []  # US-C5.1: 이용 완료 후 비움
        new = client.post(ORDERS, json=body(), headers=table_headers).json()
        assert new["sessionId"] != mine["sessionId"]
        assert [o["id"] for o in client.get(ORDERS, headers=table_headers).json()["items"]] == [new["id"]]

    def test_status_updates_are_visible_to_polling_customer(  # US-C5.2
        self, client: TestClient, table_headers: dict[str, str], admin_headers: dict[str, str]
    ) -> None:
        oid = client.post(ORDERS, json=body(), headers=table_headers).json()["id"]
        client.patch(f"/api/admin/orders/{oid}/status", json={"status": "PREPARING"}, headers=admin_headers)
        assert client.get(ORDERS, headers=table_headers).json()["items"][0]["status"] == "PREPARING"

    def test_paging_parameters_validated(self, client: TestClient, table_headers: dict[str, str]) -> None:
        for params in ({"page": -1}, {"size": 0}, {"size": 51}, {"page": "x"}):
            res = client.get(ORDERS, params=params, headers=table_headers)
            assert res.status_code == 422, params
            assert set(res.json()["fields"]) <= {"page", "size"}
