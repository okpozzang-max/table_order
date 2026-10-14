from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import schema_core, schema_order  # noqa: F401
from app.db import Database, init_schema, registered_modules

NOW = "2026-10-14T00:00:00Z"


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "t.sqlite3")
    init_schema(database)
    return database


def add_table(conn: sqlite3.Connection, number: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO tables(table_number, password_hash, created_at) VALUES (?, 'h', ?)", (number, NOW)
    )
    return int(cur.lastrowid)


def add_session(conn: sqlite3.Connection, sid: str, table_id: int, ended: str | None = None) -> None:
    conn.execute("INSERT INTO table_sessions(id, table_id, started_at, ended_at) VALUES (?, ?, ?, ?)", (sid, table_id, NOW, ended))


def add_order(conn: sqlite3.Connection, sid: str, table_id: int, client_id: str = "c1", status: str = "PENDING", total: int = 1000) -> int:
    cur = conn.execute(
        "INSERT INTO orders(session_id, table_id, client_order_id, status, total_amount, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, table_id, client_id, status, total, NOW),
    )
    return int(cur.lastrowid)


def add_item(conn: sqlite3.Connection, order_id: int, qty: int = 1, price: int = 1000) -> None:
    conn.execute(
        "INSERT INTO order_items(order_id, menu_id, menu_name, quantity, unit_price) VALUES (?, 1, 'm', ?, ?)",
        (order_id, qty, price),
    )


def test_modules_registered_in_order() -> None:
    names = [m.name for m in registered_modules()]
    assert names.index("core") < names.index("order")


def test_creates_tables_and_records_version(db: Database) -> None:
    with db.connection() as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("SELECT version FROM schema_version WHERE module='order'").fetchone()
    assert {"table_sessions", "orders", "order_items", "order_history", "order_history_items"} <= names
    assert version["version"] == 1


def test_init_is_idempotent(db: Database) -> None:
    init_schema(db)
    init_schema(db)
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM schema_version WHERE module='order'").fetchone()["n"] == 1


class TestSessions:
    def test_only_one_active_session_per_table(self, db: Database) -> None:
        with db.transaction() as conn:
            t = add_table(conn)
            add_session(conn, "sess_a", t)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_session(conn, "sess_b", 1)

    def test_new_session_allowed_after_previous_ended(self, db: Database) -> None:
        with db.transaction() as conn:
            t = add_table(conn)
            add_session(conn, "sess_a", t, ended=NOW)
            add_session(conn, "sess_b", t)
            add_session(conn, "sess_c", t, ended=NOW)  # 종료된 세션은 여러 개 가능

    def test_other_tables_have_their_own_active_session(self, db: Database) -> None:
        with db.transaction() as conn:
            add_session(conn, "sess_a", add_table(conn, 1))
            add_session(conn, "sess_b", add_table(conn, 2))

    def test_session_requires_existing_table(self, db: Database) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_session(conn, "sess_x", 999)


class TestOrders:
    def _setup(self, db: Database) -> tuple[int, str]:
        with db.transaction() as conn:
            t = add_table(conn)
            add_session(conn, "sess_a", t)
        return t, "sess_a"

    def test_client_order_id_unique_per_table(self, db: Database) -> None:
        t, sid = self._setup(db)
        with db.transaction() as conn:
            add_order(conn, sid, t, "same")
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_order(conn, sid, t, "same")

    def test_same_client_order_id_allowed_on_other_table(self, db: Database) -> None:
        t, sid = self._setup(db)
        with db.transaction() as conn:
            t2 = add_table(conn, 2)
            add_session(conn, "sess_b", t2)
            add_order(conn, sid, t, "same")
            add_order(conn, "sess_b", t2, "same")

    def test_status_check(self, db: Database) -> None:
        t, sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_order(conn, sid, t, status="DONE")

    def test_total_must_be_positive(self, db: Database) -> None:
        t, sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_order(conn, sid, t, total=0)

    @pytest.mark.parametrize("qty", [0, 21])
    def test_item_quantity_check(self, db: Database, qty: int) -> None:
        t, sid = self._setup(db)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_item(conn, add_order(conn, sid, t), qty=qty)

    def test_items_have_no_menu_foreign_key(self, db: Database) -> None:
        # menus에 해당 ID가 없어도 저장된다 (스냅샷 설계)
        t, sid = self._setup(db)
        with db.transaction() as conn:
            add_item(conn, add_order(conn, sid, t))

    def test_deleting_order_cascades_to_items(self, db: Database) -> None:
        t, sid = self._setup(db)
        with db.transaction() as conn:
            oid = add_order(conn, sid, t)
            add_item(conn, oid)
            add_item(conn, oid)
        with db.transaction() as conn:
            conn.execute("DELETE FROM orders WHERE id = ?", (oid,))
        with db.connection() as conn:
            assert conn.execute("SELECT COUNT(*) AS n FROM order_items").fetchone()["n"] == 0

    def test_order_ids_are_never_reused(self, db: Database) -> None:
        t, sid = self._setup(db)
        with db.transaction() as conn:
            first = add_order(conn, sid, t, "a")
            conn.execute("DELETE FROM orders WHERE id = ?", (first,))
            second = add_order(conn, sid, t, "b")
        assert second > first

    def test_order_requires_existing_session(self, db: Database) -> None:
        with db.transaction() as conn:
            t = add_table(conn)
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                add_order(conn, "sess_missing", t)


class TestHistory:
    def test_history_unique_client_order_id_and_cascade(self, db: Database) -> None:
        with db.transaction() as conn:
            t = add_table(conn)
            add_session(conn, "sess_a", t, ended=NOW)
            conn.execute(
                "INSERT INTO order_history(order_id, session_id, table_id, client_order_id, status, total_amount, created_at, completed_at) "
                "VALUES (7, 'sess_a', ?, 'c1', 'PENDING', 1000, ?, ?)",
                (t, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO order_history_items(order_id, menu_id, menu_name, quantity, unit_price) VALUES (7, 1, 'm', 1, 1000)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO order_history(order_id, session_id, table_id, client_order_id, status, total_amount, created_at, completed_at) "
                    "VALUES (8, 'sess_a', 1, 'c1', 'PENDING', 1000, ?, ?)",
                    (NOW, NOW),
                )
        with db.transaction() as conn:
            conn.execute("DELETE FROM order_history WHERE order_id = 7")
        with db.connection() as conn:
            assert conn.execute("SELECT COUNT(*) AS n FROM order_history_items").fetchone()["n"] == 0
