from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import schema_core  # noqa: F401
from app.db import Database, SchemaModule, SchemaVersionError, init_schema


def _insert_menu(conn: sqlite3.Connection, name: str, category: str = "메인", price: int = 1000, deleted: str | None = None) -> None:
    conn.execute(
        "INSERT INTO menus(name, price, category, category_order, display_order, created_at, updated_at, deleted_at) "
        "VALUES (?, ?, ?, 1, 1, 't', 't', ?)",
        (name, price, category, deleted),
    )


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "x" / "t.sqlite3")  # 상위 디렉토리가 없어도 생성되어야 한다
    init_schema(database)
    return database


def test_creates_parent_directory_and_core_tables(db: Database) -> None:
    assert db.path.parent.is_dir()
    with db.connection() as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("SELECT version FROM schema_version WHERE module='core'").fetchone()
    assert {"menus", "tables", "login_attempts", "schema_version"} <= names
    assert version["version"] == 1


def test_init_schema_is_idempotent(db: Database) -> None:
    init_schema(db)
    init_schema(db)
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM schema_version WHERE module='core'").fetchone()["n"] == 1


def test_connection_pragmas(db: Database) -> None:
    with db.connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_unique_menu_name_applies_only_to_active_rows(db: Database) -> None:
    with db.transaction() as conn:
        _insert_menu(conn, "김치찌개")
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            _insert_menu(conn, "김치찌개")
    with db.transaction() as conn:
        conn.execute("UPDATE menus SET deleted_at='2026-01-01T00:00:00Z'")
        _insert_menu(conn, "김치찌개")  # 삭제된 메뉴와 같은 이름은 허용
        _insert_menu(conn, "김치찌개", category="사이드")  # 다른 카테고리도 허용


def test_price_check_constraint(db: Database) -> None:
    for bad in (99, 1_000_001):
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                _insert_menu(conn, f"m{bad}", price=bad)


def test_table_number_constraints(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT INTO tables(table_number, password_hash, created_at) VALUES (1, 'h', 't')")
    for bad in (1, 0, 1000):  # 중복, 범위 밖
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute("INSERT INTO tables(table_number, password_hash, created_at) VALUES (?, 'h', 't')", (bad,))


def test_transaction_rolls_back_on_error(db: Database) -> None:
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            _insert_menu(conn, "임시")
            raise RuntimeError("boom")
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM menus").fetchone()["n"] == 0


def test_transaction_commits_on_success_and_tolerates_early_commit(db: Database) -> None:
    with db.transaction() as conn:
        _insert_menu(conn, "a")
        conn.execute("COMMIT")  # 서비스가 일찍 커밋해도 종료 처리가 깨지지 않는다
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM menus").fetchone()["n"] == 1


def test_refuses_to_start_when_db_schema_is_newer(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute("UPDATE schema_version SET version = 99 WHERE module = 'core'")
    with pytest.raises(SchemaVersionError):
        init_schema(db)


def test_custom_modules_are_applied_once_with_current_version(tmp_path: Path) -> None:
    calls: list[int | None] = []

    def apply(conn: sqlite3.Connection, current: int | None) -> None:
        calls.append(current)
        conn.execute("CREATE TABLE IF NOT EXISTS extra(id INTEGER)")

    database = Database(tmp_path / "m.sqlite3")
    mod_v1 = SchemaModule("extra", 1, apply)
    init_schema(database, [mod_v1])
    init_schema(database, [mod_v1])
    assert calls == [None]  # 같은 버전은 다시 적용하지 않는다
    init_schema(database, [SchemaModule("extra", 2, apply)])
    assert calls == [None, 1]  # 업그레이드 시 현재 버전을 전달한다
