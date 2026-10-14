from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from app.errors import Unauthorized, ValidationFailed
from app.schemas import (
    AdminLoginRequest,
    MenuInput,
    ReorderRequest,
    TableLoginRequest,
    validate_admin_login,
    validate_menu_input,
    validate_reorder,
    validate_table_login,
)
from app.security import TokenService, hash_password, verify_password
from tests.conftest import FakeClock


class TestPasswords:
    def test_hash_and_verify(self) -> None:
        h = hash_password("secret1234", 4)
        assert h.startswith("$2")
        assert verify_password("secret1234", h)
        assert not verify_password("other", h)

    def test_over_72_bytes_is_rejected_not_truncated(self) -> None:
        with pytest.raises(ValueError):
            hash_password("a" * 73, 4)
        h = hash_password("a" * 72, 4)
        assert not verify_password("a" * 73, h)  # 절단되어 통과하면 안 된다

    def test_invalid_hash_is_false(self) -> None:
        assert not verify_password("x", "not-a-hash")


class TestTokens:
    def _svc(self, clock: FakeClock, *, store_id: str = "demo", secret: str = "s" * 32) -> TokenService:
        return TokenService(secret=secret, ttl_hours=16, store_id=store_id, clock=clock)

    def test_admin_token_claims_and_16_hour_expiry(self, clock: FakeClock) -> None:
        svc = self._svc(clock)
        issued = svc.create_admin_token("admin")
        assert issued.expires_at == clock() + timedelta(hours=16)
        claims = svc.decode(issued.token, expected_role="admin")
        assert (claims.sub, claims.role, claims.store_id) == ("admin:admin", "admin", "demo")
        assert claims.exp - claims.iat == 16 * 3600

    def test_table_token_claims(self, clock: FakeClock) -> None:
        svc = self._svc(clock)
        claims = svc.decode(svc.create_table_token(7, 3).token, expected_role="table")
        assert (claims.table_id, claims.table_number, claims.role) == (7, 3, "table")

    def test_expired_token_is_rejected_using_injected_clock(self, clock: FakeClock) -> None:
        svc = self._svc(clock)
        token = svc.create_admin_token("admin").token
        clock.advance(16 * 3600 - 1)
        svc.decode(token, expected_role="admin")  # 아직 유효
        clock.advance(1)
        with pytest.raises(Unauthorized):
            svc.decode(token, expected_role="admin")

    def test_wrong_role_is_rejected(self, clock: FakeClock) -> None:
        svc = self._svc(clock)
        with pytest.raises(Unauthorized):
            svc.decode(svc.create_admin_token("admin").token, expected_role="table")
        with pytest.raises(Unauthorized):
            svc.decode(svc.create_table_token(1, 1).token, expected_role="admin")

    def test_tampered_or_foreign_tokens_are_rejected(self, clock: FakeClock) -> None:
        svc = self._svc(clock)
        token = svc.create_admin_token("admin").token
        with pytest.raises(Unauthorized):
            svc.decode(token[:-2] + ("AA" if token[-2:] != "AA" else "BB"), expected_role="admin")
        with pytest.raises(Unauthorized):
            svc.decode(self._svc(clock, secret="o" * 32).create_admin_token("admin").token, expected_role="admin")
        with pytest.raises(Unauthorized):
            svc.decode("garbage", expected_role="admin")

    def test_other_store_token_is_rejected(self, clock: FakeClock) -> None:
        other = self._svc(clock, store_id="other")
        with pytest.raises(Unauthorized):
            self._svc(clock).decode(other.create_admin_token("admin").token, expected_role="admin")

    def test_alg_none_token_is_rejected(self, clock: FakeClock) -> None:
        now = int(clock().timestamp())
        forged = jwt.encode(
            {"sub": "admin:admin", "role": "admin", "storeId": "demo", "iat": now, "exp": now + 3600},
            key="",
            algorithm="none",
        )
        with pytest.raises(Unauthorized):
            self._svc(clock).decode(forged, expected_role="admin")


class TestValidation:
    def test_table_login_boundaries(self) -> None:
        ok = validate_table_login(TableLoginRequest(storeId=" demo ", tableNumber=999, password="0000"))
        assert ok == ("demo", 999, "0000")
        for table_number in (0, 1000):
            with pytest.raises(ValidationFailed) as exc:
                validate_table_login(TableLoginRequest(storeId="demo", tableNumber=table_number, password="1234"))
            assert "tableNumber" in exc.value.fields
        for password in ("123", "12345", "12a4", ""):
            with pytest.raises(ValidationFailed) as exc:
                validate_table_login(TableLoginRequest(storeId="demo", tableNumber=1, password=password))
            assert "password" in exc.value.fields
        with pytest.raises(ValidationFailed) as exc:
            validate_table_login(TableLoginRequest(storeId="  ", tableNumber=1, password="1234"))
        assert "storeId" in exc.value.fields
        with pytest.raises(ValidationFailed) as exc:
            validate_table_login(TableLoginRequest(storeId="a" * 51, tableNumber=1, password="1234"))
        assert "storeId" in exc.value.fields

    def test_admin_login_requires_all_and_72_bytes(self) -> None:
        with pytest.raises(ValidationFailed) as exc:
            validate_admin_login(AdminLoginRequest(storeId="", username=" ", password=""))
        assert set(exc.value.fields) == {"storeId", "username", "password"}
        with pytest.raises(ValidationFailed) as exc:
            validate_admin_login(AdminLoginRequest(storeId="d", username="a", password="가" * 25))  # 75바이트
        assert "password" in exc.value.fields
        assert validate_admin_login(AdminLoginRequest(storeId=" d ", username=" a ", password=" p ")) == ("d", "a", " p ")

    @staticmethod
    def _menu(**kw: object) -> MenuInput:
        base: dict[str, object] = {
            "name": "김치찌개", "price": 9000, "description": "", "category": "메인", "imageUrl": None,
        }
        base.update(kw)
        return MenuInput(**base)  # type: ignore[arg-type]

    def test_menu_valid_input_is_trimmed(self) -> None:
        data = validate_menu_input(self._menu(name="  김치찌개 ", category=" 메인 ", description=" d ", imageUrl="  "))
        assert (data.name, data.category, data.description, data.image_url) == ("김치찌개", "메인", "d", None)

    @pytest.mark.parametrize(
        "field,value,ok",
        [
            ("name", "a" * 50, True), ("name", "a" * 51, False), ("name", "   ", False),
            ("price", 99, False), ("price", 100, True), ("price", 1_000_000, True), ("price", 1_000_001, False),
            ("description", "a" * 300, True), ("description", "a" * 301, False),
            ("category", "a" * 30, True), ("category", "a" * 31, False), ("category", "", False),
            ("imageUrl", "https://x.test/a.png", True), ("imageUrl", "http://x.test", True),
            ("imageUrl", "ftp://x.test/a", False), ("imageUrl", "not a url", False), ("imageUrl", "https://", False),
            ("imageUrl", "javascript:alert(1)", False), ("imageUrl", "https://x.test/" + "a" * 2050, False),
        ],
    )
    def test_menu_field_boundaries(self, field: str, value: object, ok: bool) -> None:
        if ok:
            validate_menu_input(self._menu(**{field: value}))
        else:
            with pytest.raises(ValidationFailed) as exc:
                validate_menu_input(self._menu(**{field: value}))
            assert field in exc.value.fields

    def test_menu_collects_all_errors(self) -> None:
        with pytest.raises(ValidationFailed) as exc:
            validate_menu_input(self._menu(name="", price=1, category="", imageUrl="ftp://x"))
        assert set(exc.value.fields) == {"name", "price", "category", "imageUrl"}

    def test_reorder_category_validation(self) -> None:
        assert validate_reorder(ReorderRequest(category=" 메인 ", orderedIds=[2, 1])) == ("메인", [2, 1])
        with pytest.raises(ValidationFailed):
            validate_reorder(ReorderRequest(category="", orderedIds=[]))
