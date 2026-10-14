from __future__ import annotations

import pytest

from app.deps import AppContainer
from app.errors import AccountLocked, InvalidCredentials
from app.main import build_container
from tests.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, STORE_ID, TABLE_PASSWORD, FakeClock


def _attempts(container: AppContainer, scope: str, key: str):  # type: ignore[no-untyped-def]
    with container.db.connection() as conn:
        return conn.execute(
            "SELECT failure_count, locked_until FROM login_attempts WHERE scope=? AND key=?", (scope, key)
        ).fetchone()


class TestAdminLogin:
    def test_success_issues_16h_token(self, seeded: AppContainer, clock: FakeClock) -> None:
        res = seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
        assert res.access_token
        assert (res.expires_at - clock()).total_seconds() == 16 * 3600

    @pytest.mark.parametrize(
        "store,user,pw",
        [("other", ADMIN_USERNAME, ADMIN_PASSWORD), (STORE_ID, "root", ADMIN_PASSWORD), (STORE_ID, ADMIN_USERNAME, "nope")],
    )
    def test_wrong_credentials(self, seeded: AppContainer, store: str, user: str, pw: str) -> None:
        with pytest.raises(InvalidCredentials):
            seeded.auth.login_admin(store, user, pw)

    def test_case_sensitive(self, seeded: AppContainer) -> None:
        with pytest.raises(InvalidCredentials):
            seeded.auth.login_admin(STORE_ID.upper(), ADMIN_USERNAME, ADMIN_PASSWORD)
        with pytest.raises(InvalidCredentials):
            seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME.upper(), ADMIN_PASSWORD)

    def test_fifth_consecutive_failure_locks_for_15_minutes(self, seeded: AppContainer) -> None:
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        with pytest.raises(AccountLocked) as exc:
            seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        assert exc.value.retry_after_seconds == 900

    def test_correct_password_is_rejected_while_locked_and_remaining_decreases(
        self, seeded: AppContainer, clock: FakeClock
    ) -> None:
        for _ in range(5):
            with pytest.raises((InvalidCredentials, AccountLocked)):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        clock.advance(300)
        with pytest.raises(AccountLocked) as exc:
            seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
        assert exc.value.retry_after_seconds == 600

    def test_lock_expires_and_counter_restarts(self, seeded: AppContainer, clock: FakeClock) -> None:
        for _ in range(5):
            with pytest.raises((InvalidCredentials, AccountLocked)):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        clock.advance(15 * 60 + 1)
        # 만료 후 첫 시도부터 다시 집계: 4번 실패해도 잠기지 않는다
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        assert seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD).access_token
        assert _attempts(seeded, "admin", "account") is None  # 성공하면 초기화

    def test_success_resets_failure_count(self, seeded: AppContainer) -> None:
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD)
        for _ in range(4):  # 다시 4번 실패해도 잠기지 않는다
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")

    def test_changing_username_does_not_evade_lock(self, seeded: AppContainer) -> None:
        names = ["a", "b", "c", "d", "e"]
        results = []
        for name in names:
            try:
                seeded.auth.login_admin(STORE_ID, name, "bad")
            except (InvalidCredentials, AccountLocked) as exc:
                results.append(type(exc))
        assert results[-1] is AccountLocked
        with pytest.raises(AccountLocked):
            seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD)

    def test_lock_survives_restart(self, seeded: AppContainer, clock: FakeClock) -> None:
        for _ in range(5):
            with pytest.raises((InvalidCredentials, AccountLocked)):
                seeded.auth.login_admin(STORE_ID, ADMIN_USERNAME, "bad")
        restarted = build_container(seeded.settings, clock)  # 같은 DB 파일, 새 인스턴스
        with pytest.raises(AccountLocked):
            restarted.auth.login_admin(STORE_ID, ADMIN_USERNAME, ADMIN_PASSWORD)


class TestTableLogin:
    def test_success_returns_table_identity(self, seeded: AppContainer) -> None:
        res = seeded.auth.login_table(STORE_ID, 3, TABLE_PASSWORD)
        assert (res.table_number,) == (3,)
        assert res.table_id > 0 and res.access_token

    def test_wrong_password_unknown_table_and_wrong_store_look_the_same(self, seeded: AppContainer) -> None:
        for args in [(STORE_ID, 1, "9999"), (STORE_ID, 77, TABLE_PASSWORD), ("other", 1, TABLE_PASSWORD)]:
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table(*args)

    def test_tenth_failure_locks_for_5_minutes(self, seeded: AppContainer, clock: FakeClock) -> None:
        for _ in range(9):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table(STORE_ID, 1, "0000")
        with pytest.raises(AccountLocked) as exc:
            seeded.auth.login_table(STORE_ID, 1, "0000")
        assert exc.value.retry_after_seconds == 300
        with pytest.raises(AccountLocked):  # 올바른 비밀번호도 거부
            seeded.auth.login_table(STORE_ID, 1, TABLE_PASSWORD)
        clock.advance(301)
        assert seeded.auth.login_table(STORE_ID, 1, TABLE_PASSWORD).table_number == 1

    def test_lock_is_per_table(self, seeded: AppContainer) -> None:
        for _ in range(10):
            with pytest.raises((InvalidCredentials, AccountLocked)):
                seeded.auth.login_table(STORE_ID, 1, "0000")
        assert seeded.auth.login_table(STORE_ID, 2, TABLE_PASSWORD).table_number == 2

    def test_unknown_table_and_wrong_store_are_not_counted(self, seeded: AppContainer) -> None:
        for _ in range(15):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table(STORE_ID, 77, "0000")
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table("other", 1, "0000")
        with seeded.db.connection() as conn:
            assert conn.execute("SELECT COUNT(*) AS n FROM login_attempts").fetchone()["n"] == 0
        assert seeded.auth.login_table(STORE_ID, 1, TABLE_PASSWORD).table_number == 1

    def test_success_resets_table_counter(self, seeded: AppContainer) -> None:
        for _ in range(9):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table(STORE_ID, 1, "0000")
        seeded.auth.login_table(STORE_ID, 1, TABLE_PASSWORD)
        for _ in range(9):
            with pytest.raises(InvalidCredentials):
                seeded.auth.login_table(STORE_ID, 1, "0000")
        assert seeded.auth.login_table(STORE_ID, 1, TABLE_PASSWORD).table_number == 1

    def test_password_is_stored_hashed(self, seeded: AppContainer) -> None:
        with seeded.db.connection() as conn:
            hashes = [r["password_hash"] for r in conn.execute("SELECT password_hash FROM tables")]
        assert hashes and all(h.startswith("$2") and TABLE_PASSWORD not in h for h in hashes)
