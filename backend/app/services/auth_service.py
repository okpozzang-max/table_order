"""관리자/테이블 로그인과 잠금 (business-logic-model 3, 4절).

비밀번호 검증(bcrypt, 수백 ms)은 쓰기 잠금 밖에서 수행하고, 결과 반영은 짧은 BEGIN IMMEDIATE 트랜잭션으로 한다.
잠금 판정은 결과 반영 직전에 한 번 더 확인해, 동시 시도가 잠금을 우회하지 못하게 한다.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import Settings
from ..db import Database
from ..errors import AccountLocked, InvalidCredentials
from ..security import TokenService, hash_password, verify_password
from ..timeutil import Clock, parse_iso, utc_iso

ADMIN_SCOPE = "admin"
ADMIN_KEY = "account"  # 관리자 계정은 하나이므로 제출된 사용자명과 무관하게 한 키로 집계
TABLE_SCOPE = "table"


@dataclass(frozen=True)
class AdminLoginResult:
    access_token: str
    expires_at: datetime


@dataclass(frozen=True)
class TableLoginResult:
    access_token: str
    expires_at: datetime
    table_id: int
    table_number: int


class AuthService:
    def __init__(self, *, settings: Settings, db: Database, tokens: TokenService, clock: Clock) -> None:
        self._settings = settings
        self._db = db
        self._tokens = tokens
        self._clock = clock
        # 존재하지 않는 계정/테이블에도 같은 비용의 해시 검증을 수행하기 위한 더미 해시
        self._dummy_hash = hash_password("not-a-real-password", settings.bcrypt_rounds)

    # ---------- 관리자 ----------

    def login_admin(self, store_id: str, username: str, password: str) -> AdminLoginResult:
        s = self._settings
        remaining = self._locked_seconds(ADMIN_SCOPE, ADMIN_KEY)
        if remaining:
            raise AccountLocked(remaining)

        creds_ok = store_id == s.store_id and username == s.admin_username
        # 매장/사용자명이 틀려도 비밀번호 해시 검증을 수행해 응답 시간 차이를 줄인다
        password_ok = verify_password(password, s.admin_password_hash)
        ok = creds_ok and password_ok

        lock_seconds: int | None = None
        with self._db.transaction() as conn:
            remaining = self._remaining_lock(conn, ADMIN_SCOPE, ADMIN_KEY)
            if remaining:
                lock_seconds = remaining
            elif ok:
                self._clear(conn, ADMIN_SCOPE, ADMIN_KEY)
            else:
                lock_seconds = self._register_failure(
                    conn, ADMIN_SCOPE, ADMIN_KEY, s.admin_login_max_failures, s.admin_login_lock_minutes
                )
        # 기록을 커밋한 뒤에 예외를 던진다 (실패 횟수가 롤백으로 사라지지 않게)
        if lock_seconds:
            raise AccountLocked(lock_seconds)
        if not ok:
            raise InvalidCredentials()

        issued = self._tokens.create_admin_token(s.admin_username)
        return AdminLoginResult(access_token=issued.token, expires_at=issued.expires_at)

    # ---------- 테이블 ----------

    def login_table(self, store_id: str, table_number: int, password: str) -> TableLoginResult:
        s = self._settings
        if store_id != s.store_id:
            verify_password(password, self._dummy_hash)
            raise InvalidCredentials()

        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT id, table_number, password_hash FROM tables WHERE table_number = ?", (table_number,)
            ).fetchone()
        if row is None:
            verify_password(password, self._dummy_hash)
            raise InvalidCredentials()

        key = str(table_number)
        remaining = self._locked_seconds(TABLE_SCOPE, key)
        if remaining:
            raise AccountLocked(remaining)

        ok = verify_password(password, row["password_hash"])

        lock_seconds: int | None = None
        with self._db.transaction() as conn:
            remaining = self._remaining_lock(conn, TABLE_SCOPE, key)
            if remaining:
                lock_seconds = remaining
            elif ok:
                self._clear(conn, TABLE_SCOPE, key)
            else:
                lock_seconds = self._register_failure(
                    conn, TABLE_SCOPE, key, s.table_login_max_failures, s.table_login_lock_minutes
                )
        if lock_seconds:
            raise AccountLocked(lock_seconds)
        if not ok:
            raise InvalidCredentials()

        issued = self._tokens.create_table_token(row["id"], row["table_number"])
        return TableLoginResult(
            access_token=issued.token,
            expires_at=issued.expires_at,
            table_id=row["id"],
            table_number=row["table_number"],
        )

    # ---------- 잠금 내부 ----------

    def _locked_seconds(self, scope: str, key: str) -> int:
        with self._db.transaction() as conn:
            return self._remaining_lock(conn, scope, key)

    def _remaining_lock(self, conn: sqlite3.Connection, scope: str, key: str) -> int:
        """남은 잠금 초(없으면 0). 잠금이 만료되었다면 행을 초기화한다."""
        row = conn.execute(
            "SELECT locked_until FROM login_attempts WHERE scope = ? AND key = ?", (scope, key)
        ).fetchone()
        if row is None or not row["locked_until"]:
            return 0
        now = self._clock()
        until = parse_iso(row["locked_until"])
        if until > now:
            return max(1, math.ceil((until - now).total_seconds()))
        conn.execute(
            "UPDATE login_attempts SET failure_count = 0, locked_until = NULL, updated_at = ? "
            "WHERE scope = ? AND key = ?",
            (utc_iso(now), scope, key),
        )
        return 0

    def _clear(self, conn: sqlite3.Connection, scope: str, key: str) -> None:
        conn.execute("DELETE FROM login_attempts WHERE scope = ? AND key = ?", (scope, key))

    def _register_failure(
        self, conn: sqlite3.Connection, scope: str, key: str, max_failures: int, lock_minutes: int
    ) -> int | None:
        """실패를 기록한다. 잠금이 걸리면 잠금 시간(초)을 반환한다."""
        now = self._clock()
        row = conn.execute(
            "SELECT failure_count FROM login_attempts WHERE scope = ? AND key = ?", (scope, key)
        ).fetchone()
        count = (row["failure_count"] if row else 0) + 1
        locked_until: str | None = None
        lock_seconds: int | None = None
        if count >= max_failures:
            locked_until = utc_iso(now + timedelta(minutes=lock_minutes))
            lock_seconds = lock_minutes * 60
            count = 0
        conn.execute(
            "INSERT INTO login_attempts(scope, key, failure_count, locked_until, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(scope, key) DO UPDATE SET failure_count = excluded.failure_count, "
            "locked_until = excluded.locked_until, updated_at = excluded.updated_at",
            (scope, key, count, locked_until, utc_iso(now)),
        )
        return lock_seconds
