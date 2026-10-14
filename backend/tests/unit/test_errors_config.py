from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigError, Settings, load_settings
from app.errors import (
    AccountLocked,
    DuplicateTable,
    InvalidCredentials,
    InvalidTransition,
    MenuUnavailable,
    NoActiveSession,
    NotFound,
    PriceChanged,
    Unauthorized,
    ValidationFailed,
    error_body,
    fields_from_request_errors,
)
from app.security import hash_password


class TestErrors:
    def test_error_body_omits_empty_keys(self) -> None:
        assert error_body("NOT_FOUND") == {"code": "NOT_FOUND"}
        assert error_body("X", "msg", fields={"a": "b"}, retry_after_seconds=3, details={"k": 1}) == {
            "code": "X",
            "message": "msg",
            "fields": {"a": "b"},
            "retryAfterSeconds": 3,
            "details": {"k": 1},
        }

    def test_domain_errors_map_to_status_and_code(self) -> None:
        cases = [
            (ValidationFailed({"name": "x"}), 422, "VALIDATION_ERROR"),
            (InvalidCredentials(), 401, "INVALID_CREDENTIALS"),
            (Unauthorized(), 401, "UNAUTHORIZED"),
            (AccountLocked(900), 429, "ACCOUNT_LOCKED"),
            (NotFound(), 404, "NOT_FOUND"),
        ]
        for exc, status, code in cases:
            assert exc.status_code == status
            assert exc.to_body()["code"] == code

    def test_locked_error_has_retry_after(self) -> None:
        exc = AccountLocked(900)
        assert exc.to_body()["retryAfterSeconds"] == 900
        assert exc.headers == {"Retry-After": "900"}
        assert AccountLocked(0).retry_after_seconds == 1  # 최소 1초

    def test_unauthorized_has_www_authenticate(self) -> None:
        assert Unauthorized().headers == {"WWW-Authenticate": "Bearer"}

    def test_validation_fields_are_in_body(self) -> None:
        body = ValidationFailed({"price": "p"}).to_body()
        assert body["fields"] == {"price": "p"}

    def test_pydantic_errors_to_fields(self) -> None:
        errors = [
            {"loc": ("body", "price"), "msg": "x", "type": "int_type"},
            {"loc": ("body", "storeId"), "msg": "x", "type": "missing"},
            {"loc": ("body",), "msg": "x", "type": "json_invalid"},
        ]
        fields = fields_from_request_errors(errors)
        assert "가격" in fields["price"]
        assert fields["storeId"]  # 모호한 필드명은 일반 문구
        assert "body" in fields


class TestOrderErrors:
    def test_status_and_code(self) -> None:
        cases = [
            (MenuUnavailable([3]), "MENU_UNAVAILABLE"),
            (PriceChanged([{"menuId": 1, "price": 100}]), "PRICE_CHANGED"),
            (InvalidTransition("PENDING", "COMPLETED"), "INVALID_TRANSITION"),
            (NoActiveSession(), "NO_ACTIVE_SESSION"),
            (DuplicateTable(3), "DUPLICATE_TABLE"),
        ]
        for exc, code in cases:
            assert exc.status_code == 409
            assert exc.to_body()["code"] == code
            assert exc.to_body()["message"]

    def test_menu_unavailable_details_sorted_unique(self) -> None:
        body = MenuUnavailable([9, 2, 9, 5]).to_body()
        assert body["details"] == {"menuIds": [2, 5, 9]}

    def test_price_changed_details_keep_order(self) -> None:
        prices = [{"menuId": 7, "price": 9000}, {"menuId": 2, "price": 500}]
        assert PriceChanged(prices).to_body()["details"] == {"currentPrices": prices}

    def test_errors_without_details_have_no_details_key(self) -> None:
        for exc in (InvalidTransition(), NoActiveSession(), DuplicateTable()):
            assert "details" not in exc.to_body()

    def test_new_field_messages_exist(self) -> None:
        errors = [
            {"loc": ("body", "items", 0, "quantity"), "msg": "x", "type": "int_type"},
            {"loc": ("query", "page"), "msg": "x", "type": "greater_than_equal"},
            {"loc": ("query", "from"), "msg": "x", "type": "date_parsing"},
            {"loc": ("path", "orderId"), "msg": "x", "type": "int_parsing"},
        ]
        fields = fields_from_request_errors(errors)
        assert set(fields) == {"items", "page", "from", "orderId"}
        assert fields["items"] == "수량은 1~20 사이로 입력해주세요."
        assert fields["from"] == "날짜 형식이 올바르지 않아요."


class TestSettings:
    def _env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: str) -> None:
        monkeypatch.chdir(tmp_path)  # 작업 디렉토리의 .env 가 섞이지 않게
        for key in [
            "STORE_ID", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "JWT_SECRET", "DB_PATH", "TOKEN_TTL_HOURS",
            "ADMIN_LOGIN_MAX_FAILURES", "BCRYPT_ROUNDS",
        ]:
            monkeypatch.delenv(key, raising=False)
        base = {
            "STORE_ID": "demo",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD_HASH": hash_password("pw", 4),
            "JWT_SECRET": "s" * 40,
        }
        base.update(overrides)
        for key, value in base.items():
            if value is not None:
                monkeypatch.setenv(key, value)

    def test_loads_with_defaults(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._env(monkeypatch, tmp_path)
        s = load_settings()
        assert s.store_id == "demo"
        assert s.token_ttl_hours == 16
        assert s.admin_login_max_failures == 5
        assert s.admin_login_lock_minutes == 15
        assert s.table_login_max_failures == 10
        assert s.table_login_lock_minutes == 5
        assert s.bcrypt_rounds == 12
        assert s.db_path.name == "table_order.sqlite3"

    def test_missing_required_names_only_keys(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._env(monkeypatch, tmp_path)
        monkeypatch.delenv("STORE_ID")
        monkeypatch.delenv("JWT_SECRET")
        with pytest.raises(ConfigError) as exc:
            load_settings()
        message = str(exc.value)
        assert "STORE_ID" in message and "JWT_SECRET" in message

    def test_short_secret_rejected_without_leaking_value(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._env(monkeypatch, tmp_path, JWT_SECRET="short-secret")
        with pytest.raises(ConfigError) as exc:
            load_settings()
        assert "JWT_SECRET" in str(exc.value)
        assert "short-secret" not in str(exc.value)

    def test_hash_must_be_bcrypt(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._env(monkeypatch, tmp_path, ADMIN_PASSWORD_HASH="plain-password")
        with pytest.raises(ConfigError) as exc:
            load_settings()
        assert "ADMIN_PASSWORD_HASH" in str(exc.value)
        assert "plain-password" not in str(exc.value)

    @pytest.mark.parametrize("key,value", [("TOKEN_TTL_HOURS", "0"), ("ADMIN_LOGIN_MAX_FAILURES", "abc"), ("BCRYPT_ROUNDS", "2")])
    def test_numeric_settings_validated(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str, value: str) -> None:
        self._env(monkeypatch, tmp_path, **{key: value})
        with pytest.raises(ConfigError) as exc:
            load_settings()
        assert key in str(exc.value)

    def test_reads_dotenv_file_with_quoted_hash(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._env(monkeypatch, tmp_path)
        for key in ["STORE_ID", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "JWT_SECRET"]:
            monkeypatch.delenv(key)
        hashed = hash_password("pw", 4)
        (tmp_path / ".env").write_text(
            f"STORE_ID=demo\nADMIN_USERNAME=admin\nADMIN_PASSWORD_HASH='{hashed}'\nJWT_SECRET={'k' * 40}\n",
            encoding="utf-8",
        )
        s = Settings()  # type: ignore[call-arg]
        assert s.admin_password_hash == hashed



class TestOrderSettings:
    """backend-order가 추가한 설정: TIMEZONE, SSE_KEEPALIVE_SECONDS, SSE_QUEUE_SIZE."""

    def _load(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **extra: str) -> Settings:
        monkeypatch.chdir(tmp_path)
        for key in ["TIMEZONE", "SSE_KEEPALIVE_SECONDS", "SSE_QUEUE_SIZE"]:
            monkeypatch.delenv(key, raising=False)
        base = {
            "STORE_ID": "demo",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD_HASH": hash_password("pw", 4),
            "JWT_SECRET": "s" * 40,
            **extra,
        }
        for key, value in base.items():
            monkeypatch.setenv(key, value)
        return load_settings()

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = self._load(monkeypatch, tmp_path)
        assert s.timezone == "Asia/Seoul"
        assert s.sse_keepalive_seconds == 15
        assert s.sse_queue_size == 100

    def test_overrides(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        s = self._load(monkeypatch, tmp_path, TIMEZONE="UTC", SSE_KEEPALIVE_SECONDS="1", SSE_QUEUE_SIZE="5")
        assert (s.timezone, s.sse_keepalive_seconds, s.sse_queue_size) == ("UTC", 1, 5)

    def test_unknown_timezone_names_only_the_key(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        with pytest.raises(ConfigError) as exc:
            self._load(monkeypatch, tmp_path, TIMEZONE="Mars/Olympus")
        assert "TIMEZONE" in str(exc.value)
        assert "Mars/Olympus" not in str(exc.value)

    @pytest.mark.parametrize("key", ["SSE_KEEPALIVE_SECONDS", "SSE_QUEUE_SIZE"])
    @pytest.mark.parametrize("value", ["0", "-1", "abc"])
    def test_sse_numbers_must_be_positive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str, value: str
    ) -> None:
        with pytest.raises(ConfigError) as exc:
            self._load(monkeypatch, tmp_path, **{key: value})
        assert key in str(exc.value)
