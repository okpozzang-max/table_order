from __future__ import annotations

from fastapi.testclient import TestClient

from app.deps import AppContainer
from tests.conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    STORE_ID,
    TABLE_PASSWORD,
    FakeClock,
    bearer,
    login_admin,
    login_table,
)

ADMIN_LOGIN = "/api/admin/auth/login"
TABLE_LOGIN = "/api/customer/auth/login"


def admin_body(**kw: object) -> dict[str, object]:
    body: dict[str, object] = {"storeId": STORE_ID, "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    body.update(kw)
    return body


def table_body(**kw: object) -> dict[str, object]:
    body: dict[str, object] = {"storeId": STORE_ID, "tableNumber": 1, "password": TABLE_PASSWORD}
    body.update(kw)
    return body


class TestAdminLoginApi:
    def test_success(self, client: TestClient, clock: FakeClock) -> None:  # US-A1.1
        res = client.post(ADMIN_LOGIN, json=admin_body())
        assert res.status_code == 200
        body = res.json()
        assert set(body) == {"accessToken", "expiresAt"}
        assert body["expiresAt"] == "2026-10-14T16:00:00Z"  # 발급 후 16시간, UTC ISO 8601

    def test_wrong_credentials_do_not_reveal_which_field(self, client: TestClient) -> None:
        for body in (admin_body(password="x"), admin_body(username="root"), admin_body(storeId="other")):
            res = client.post(ADMIN_LOGIN, json=body)
            assert res.status_code == 401
            assert res.json()["code"] == "INVALID_CREDENTIALS"

    def test_validation_errors_are_per_field(self, client: TestClient) -> None:  # US-E7 형식
        res = client.post(ADMIN_LOGIN, json=admin_body(storeId="", username=" ", password=""))
        assert res.status_code == 422
        body = res.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert set(body["fields"]) == {"storeId", "username", "password"}

    def test_lockout_flow(self, client: TestClient, clock: FakeClock) -> None:  # US-E4
        for _ in range(4):
            assert client.post(ADMIN_LOGIN, json=admin_body(password="bad")).status_code == 401
        res = client.post(ADMIN_LOGIN, json=admin_body(password="bad"))
        assert res.status_code == 429
        assert res.json() == {"code": "ACCOUNT_LOCKED", "message": res.json()["message"], "retryAfterSeconds": 900}
        assert res.headers["Retry-After"] == "900"

        clock.advance(100)
        locked = client.post(ADMIN_LOGIN, json=admin_body())  # 올바른 정보여도 거부
        assert locked.status_code == 429
        assert locked.json()["retryAfterSeconds"] == 800

        clock.advance(801)
        assert client.post(ADMIN_LOGIN, json=admin_body()).status_code == 200

    def test_non_json_and_missing_body(self, client: TestClient) -> None:
        res = client.post(ADMIN_LOGIN, content="not json", headers={"Content-Type": "application/json"})
        assert res.status_code == 422 and "body" in res.json()["fields"]
        res = client.post(ADMIN_LOGIN, json={})
        assert res.status_code == 422 and res.json()["code"] == "VALIDATION_ERROR"


class TestTableLoginApi:
    def test_success_returns_identity_and_token(self, client: TestClient) -> None:  # US-C1.1
        res = client.post(TABLE_LOGIN, json=table_body(tableNumber=2))
        assert res.status_code == 200
        body = res.json()
        assert set(body) == {"accessToken", "expiresAt", "tableId", "tableNumber"}
        assert body["tableNumber"] == 2

    def test_invalid_credentials(self, client: TestClient) -> None:  # US-E3
        for body in (table_body(password="9999"), table_body(tableNumber=77), table_body(storeId="other")):
            res = client.post(TABLE_LOGIN, json=body)
            assert (res.status_code, res.json()["code"]) == (401, "INVALID_CREDENTIALS")

    def test_validation(self, client: TestClient) -> None:
        res = client.post(TABLE_LOGIN, json=table_body(tableNumber=0, password="12"))
        assert res.status_code == 422
        assert set(res.json()["fields"]) == {"tableNumber", "password"}

    def test_wrong_types_are_reported_per_field(self, client: TestClient) -> None:
        res = client.post(TABLE_LOGIN, json=table_body(tableNumber="3"))
        assert res.status_code == 422
        assert "tableNumber" in res.json()["fields"]

    def test_table_lockout_returns_429(self, client: TestClient) -> None:
        for _ in range(9):
            assert client.post(TABLE_LOGIN, json=table_body(password="0000")).status_code == 401
        res = client.post(TABLE_LOGIN, json=table_body(password="0000"))
        assert res.status_code == 429 and res.json()["retryAfterSeconds"] == 300
        assert client.post(TABLE_LOGIN, json=table_body(tableNumber=2)).status_code == 200  # 다른 테이블은 영향 없음


class TestTokenEnforcement:
    def test_protected_routes_require_a_token(self, client: TestClient) -> None:  # US-E9
        for method, url in [
            ("get", "/api/customer/menus"), ("get", "/api/admin/menus"), ("post", "/api/admin/menus"),
            ("put", "/api/admin/menus/1"), ("delete", "/api/admin/menus/1"), ("put", "/api/admin/menus/reorder"),
        ]:
            res = getattr(client, method)(url)
            assert res.status_code == 401, (method, url)
            assert res.json()["code"] == "UNAUTHORIZED"
            assert res.headers["WWW-Authenticate"] == "Bearer"

    def test_garbage_and_non_bearer_headers(self, client: TestClient) -> None:
        assert client.get("/api/admin/menus", headers={"Authorization": "Bearer garbage"}).status_code == 401
        assert client.get("/api/admin/menus", headers={"Authorization": "Basic abc"}).status_code == 401
        assert client.get("/api/admin/menus", headers={"Authorization": "Bearer "}).status_code == 401

    def test_token_expires_after_16_hours(self, client: TestClient, clock: FakeClock) -> None:  # US-A1.2, E9
        admin = bearer(login_admin(client))
        table = bearer(login_table(client))
        clock.advance(16 * 3600 - 1)
        assert client.get("/api/admin/menus", headers=admin).status_code == 200
        assert client.get("/api/customer/menus", headers=table).status_code == 200
        clock.advance(1)
        for url, headers in [("/api/admin/menus", admin), ("/api/customer/menus", table)]:
            res = client.get(url, headers=headers)
            assert (res.status_code, res.json()["code"]) == (401, "UNAUTHORIZED")

    def test_admin_and_table_tokens_are_not_interchangeable(self, client: TestClient) -> None:
        admin = bearer(login_admin(client))
        table = bearer(login_table(client))
        assert client.get("/api/customer/menus", headers=admin).status_code == 401
        assert client.get("/api/admin/menus", headers=table).status_code == 401

    def test_token_of_removed_table_is_rejected(self, client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
        table = bearer(login_table(client, 4))
        container: AppContainer = app.state.container
        with container.db.transaction() as conn:
            conn.execute("DELETE FROM tables WHERE table_number = 4")
        assert client.get("/api/customer/menus", headers=table).status_code == 401
