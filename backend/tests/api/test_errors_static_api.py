from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import bearer, login_admin


class TestCommonErrors:
    def test_unknown_api_path_is_json_404(self, client: TestClient) -> None:
        for method in ("get", "post", "put", "delete"):
            res = getattr(client, method)("/api/nope")
            assert res.status_code == 404
            assert res.json()["code"] == "NOT_FOUND"
            assert res.headers["content-type"].startswith("application/json")

    def test_unsupported_method_on_known_path_is_json_error(self, client: TestClient) -> None:
        res = client.patch("/api/customer/auth/login")
        assert res.status_code in (404, 405)
        assert res.json()["code"] == "NOT_FOUND"

    def test_unhandled_exception_returns_500_without_internals(
        self, client: TestClient, app, caplog: pytest.LogCaptureFixture  # type: ignore[no-untyped-def]
    ) -> None:
        headers = bearer(login_admin(client))

        def boom() -> None:
            raise RuntimeError("secret internal detail /etc/passwd")

        app.state.container.menus.list_grouped = boom
        with caplog.at_level(logging.ERROR, logger="app"):
            res = client.get("/api/admin/menus", headers=headers)
        assert res.status_code == 500
        assert res.json()["code"] == "INTERNAL_ERROR"
        assert "secret internal detail" not in res.text and "Traceback" not in res.text
        assert any("secret internal detail" in str(r.exc_info[1]) for r in caplog.records if r.exc_info)  # 로그에는 남는다

    def test_secrets_are_not_in_error_responses(self, client: TestClient, settings) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/admin/auth/login", json={"storeId": "demo", "username": "admin", "password": "bad"})
        assert settings.jwt_secret not in res.text and settings.admin_password_hash not in res.text

    def test_openapi_and_docs_are_served_under_api_prefix(self, client: TestClient) -> None:
        assert client.get("/api/openapi.json").status_code == 200
        assert client.get("/api/docs").status_code == 200


class TestStaticServing:
    @pytest.fixture
    def served(self, settings, clock, publisher, dist_dir: Path) -> TestClient:  # type: ignore[no-untyped-def]
        (dist_dir / "assets").mkdir(parents=True)
        (dist_dir / "index.html").write_text("<html>SPA-INDEX</html>", encoding="utf-8")
        (dist_dir / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
        (dist_dir.parent / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
        return TestClient(create_app(settings, clock, publisher), raise_server_exceptions=False)

    def test_root_and_spa_routes_fall_back_to_index(self, served: TestClient) -> None:
        for path in ("/", "/customer/menu", "/admin/dashboard", "/deep/unknown/route"):
            res = served.get(path)
            assert res.status_code == 200 and "SPA-INDEX" in res.text, path

    def test_static_asset_is_served(self, served: TestClient) -> None:
        res = served.get("/assets/app.js")
        assert res.status_code == 200 and "console.log" in res.text

    def test_api_paths_are_not_swallowed_by_fallback(self, served: TestClient) -> None:
        res = served.get("/api/nope")
        assert res.status_code == 404 and res.json()["code"] == "NOT_FOUND"
        assert "SPA-INDEX" not in res.text
        assert served.get("/api").status_code == 404

    def test_real_api_still_works_with_static_enabled(self, served: TestClient) -> None:
        assert served.post("/api/admin/auth/login", json={"storeId": "demo", "username": "admin", "password": "x"}).status_code == 401

    def test_path_traversal_is_not_served(self, served: TestClient) -> None:
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt", "/..%2fsecret.txt"):
            res = served.get(path)
            assert "TOP-SECRET" not in res.text, path

    def test_non_get_on_spa_path_is_404(self, served: TestClient) -> None:
        assert served.post("/customer/menu").status_code == 404

    def test_without_dist_only_api_is_served(self, client: TestClient) -> None:
        res = client.get("/")
        assert res.status_code == 404 and res.json()["code"] == "NOT_FOUND"
