from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import RecordingPublisher

MENUS = "/api/admin/menus"


def menu_body(**kw: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "라면", "price": 4000, "description": "", "category": "분식", "imageUrl": None,
    }
    body.update(kw)
    return body


def grouped(client: TestClient, headers: dict[str, str], url: str = MENUS) -> list[dict]:
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    return res.json()


class TestListing:
    def test_customer_and_admin_see_same_grouped_menus(  # US-C2.1, C2.2, A4.1
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]
    ) -> None:
        admin_view = grouped(client, admin_headers)
        customer_view = grouped(client, table_headers, "/api/customer/menus")
        assert admin_view == customer_view
        assert [g["category"] for g in admin_view] == ["메인", "사이드", "음료", "디저트"]
        first = admin_view[0]["menus"][0]
        assert set(first) == {"id", "name", "price", "description", "category", "imageUrl", "displayOrder"}
        assert first["name"] == "김치찌개" and first["price"] == 9000 and first["displayOrder"] == 1
        assert [m["displayOrder"] for m in admin_view[0]["menus"]] == [1, 2, 3, 4]


class TestCreate:
    def test_create_returns_201_and_shows_up_for_customers(  # US-A4.2
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str], publisher: RecordingPublisher
    ) -> None:
        res = client.post(MENUS, json=menu_body(imageUrl="https://x.test/a.png", description="맛있어요"), headers=admin_headers)
        assert res.status_code == 201
        created = res.json()
        assert created["name"] == "라면" and created["imageUrl"] == "https://x.test/a.png"
        customer_view = grouped(client, table_headers, "/api/customer/menus")
        assert customer_view[-1]["category"] == "분식"
        assert customer_view[-1]["menus"][0]["id"] == created["id"]
        assert [e.type for e in publisher.events] == ["menu_changed"]

    def test_validation_errors_are_reported_per_field(self, client: TestClient, admin_headers: dict[str, str]) -> None:  # US-E7
        res = client.post(
            MENUS,
            json=menu_body(name="", price=50, category="", imageUrl="ftp://x", description="d" * 301),
            headers=admin_headers,
        )
        assert res.status_code == 422
        body = res.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert set(body["fields"]) == {"name", "price", "category", "imageUrl", "description"}
        assert "가격" in body["fields"]["price"]

    def test_wrong_types_and_missing_fields(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        res = client.post(MENUS, json=menu_body(price="9000"), headers=admin_headers)
        assert res.status_code == 422 and "price" in res.json()["fields"]
        res = client.post(MENUS, json={"price": 1000}, headers=admin_headers)
        assert res.status_code == 422
        assert {"name", "description", "category", "imageUrl"} <= set(res.json()["fields"])

    def test_duplicate_name_in_same_category(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.post(MENUS, json=menu_body(), headers=admin_headers).status_code == 201
        res = client.post(MENUS, json=menu_body(), headers=admin_headers)
        assert res.status_code == 422 and "name" in res.json()["fields"]
        assert client.post(MENUS, json=menu_body(category="다른"), headers=admin_headers).status_code == 201

    def test_input_is_trimmed(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        res = client.post(MENUS, json=menu_body(name="  우동  ", category="  분식 "), headers=admin_headers)
        assert (res.json()["name"], res.json()["category"]) == ("우동", "분식")


class TestUpdateDelete:
    def test_update(self, client: TestClient, admin_headers: dict[str, str]) -> None:  # US-A4.3
        res = client.put(f"{MENUS}/1", json=menu_body(name="김치찌개 특", price=9500, category="메인"), headers=admin_headers)
        assert res.status_code == 200
        assert (res.json()["name"], res.json()["price"], res.json()["displayOrder"]) == ("김치찌개 특", 9500, 1)

    def test_update_validation_and_not_found(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        assert client.put(f"{MENUS}/1", json=menu_body(price=1), headers=admin_headers).status_code == 422
        res = client.put(f"{MENUS}/999", json=menu_body(), headers=admin_headers)
        assert (res.status_code, res.json()["code"]) == (404, "NOT_FOUND")
        assert client.put(f"{MENUS}/abc", json=menu_body(), headers=admin_headers).status_code == 422

    def test_soft_delete_hides_menu_from_both_views(  # US-A4.3
        self, client: TestClient, admin_headers: dict[str, str], table_headers: dict[str, str]
    ) -> None:
        res = client.delete(f"{MENUS}/1", headers=admin_headers)
        assert res.status_code == 204 and res.content == b""
        for url, headers in ((MENUS, admin_headers), ("/api/customer/menus", table_headers)):
            ids = [m["id"] for g in grouped(client, headers, url) for m in g["menus"]]
            assert 1 not in ids
        assert [m["displayOrder"] for m in grouped(client, admin_headers)[0]["menus"]] == [1, 2, 3]
        assert client.delete(f"{MENUS}/1", headers=admin_headers).status_code == 404


class TestReorder:
    def test_reorder_is_routed_before_menu_id(self, client: TestClient, admin_headers: dict[str, str]) -> None:  # US-A4.4
        ids = [m["id"] for m in grouped(client, admin_headers)[0]["menus"]]
        res = client.put(f"{MENUS}/reorder", json={"category": "메인", "orderedIds": list(reversed(ids))}, headers=admin_headers)
        assert res.status_code == 204
        after = grouped(client, admin_headers)[0]["menus"]
        assert [m["id"] for m in after] == list(reversed(ids))
        assert [m["displayOrder"] for m in after] == [1, 2, 3, 4]

    def test_reorder_errors(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        ids = [m["id"] for m in grouped(client, admin_headers)[0]["menus"]]
        res = client.put(f"{MENUS}/reorder", json={"category": "메인", "orderedIds": ids[:-1]}, headers=admin_headers)
        assert res.status_code == 422 and "orderedIds" in res.json()["fields"]
        res = client.put(f"{MENUS}/reorder", json={"category": "없음", "orderedIds": []}, headers=admin_headers)
        assert res.status_code == 404
        res = client.put(f"{MENUS}/reorder", json={"category": "메인", "orderedIds": ["a"]}, headers=admin_headers)
        assert res.status_code == 422
