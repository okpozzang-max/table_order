"""SQLite 연결, 트랜잭션, 스키마 레지스트리.

- 연결은 요청(작업) 단위로 만든다. WAL, foreign_keys=ON, busy_timeout=5000.
- 트랜잭션은 BEGIN IMMEDIATE로 시작해 읽기-수정-쓰기 경쟁을 막는다.
- 스키마는 모듈별로 등록하고 schema_version에 버전을 기록한다 (backend-order가 자기 모듈을 추가).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .timeutil import utc_iso


class SchemaVersionError(Exception):
    """DB의 스키마 버전이 코드보다 높은 경우 등."""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: 파이썬이 암묵적으로 트랜잭션을 열지 않게 하고 BEGIN/COMMIT을 직접 제어한다.
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """읽기 전용 작업용 연결."""
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """블록이 정상 종료되면 커밋, 예외가 나면 롤백한다.

        커밋 후 이벤트 발행이나 예외 전파가 필요하면 블록 밖에서 처리한다.
        """
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield conn
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            else:
                if conn.in_transaction:
                    conn.execute("COMMIT")
        finally:
            conn.close()


@dataclass(frozen=True)
class SchemaModule:
    name: str
    version: int
    # apply(conn, current_version): current_version은 DB에 기록된 버전(없으면 None)
    apply: Callable[[sqlite3.Connection, int | None], None]


_REGISTRY: dict[str, SchemaModule] = {}


def register_schema(module: SchemaModule) -> None:
    """모듈을 등록한다 (이름이 같으면 교체). 적용 순서는 최초 등록 순서."""
    _REGISTRY[module.name] = module


def registered_modules() -> list[SchemaModule]:
    return list(_REGISTRY.values())


def init_schema(db: Database, modules: Sequence[SchemaModule] | None = None) -> None:
    """등록된(또는 지정한) 스키마 모듈을 적용하고 schema_version을 기록한다."""
    mods = list(modules) if modules is not None else registered_modules()
    with db.transaction() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " module TEXT PRIMARY KEY,"
            " version INTEGER NOT NULL,"
            " applied_at TEXT NOT NULL)"
        )
        for mod in mods:
            row = conn.execute("SELECT version FROM schema_version WHERE module = ?", (mod.name,)).fetchone()
            current = row["version"] if row else None
            if current is not None and current > mod.version:
                raise SchemaVersionError(
                    f"DB의 '{mod.name}' 스키마 버전({current})이 코드({mod.version})보다 높아요. 코드를 최신으로 업데이트해주세요."
                )
            if current is None or current < mod.version:
                mod.apply(conn, current)
                conn.execute(
                    "INSERT INTO schema_version(module, version, applied_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(module) DO UPDATE SET version = excluded.version, applied_at = excluded.applied_at",
                    (mod.name, mod.version, utc_iso(datetime.now(timezone.utc))),
                )
