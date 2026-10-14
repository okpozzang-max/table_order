"""order 모듈 스키마: table_sessions, orders, order_items, order_history, order_history_items.

`tables`(core 소유)를 참조하므로 core 다음에 등록/적용되어야 한다 (main.py가 import 순서로 보장).
주문 항목은 주문 시점의 메뉴 이름/가격을 복사해 저장하며 `menus`에 외래키를 두지 않는다.
"""

from __future__ import annotations

import sqlite3

from .db import SchemaModule, register_schema

ORDER_SCHEMA_VERSION = 1

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS table_sessions (
        id TEXT PRIMARY KEY,
        table_id INTEGER NOT NULL REFERENCES tables(id),
        started_at TEXT NOT NULL,
        ended_at TEXT
    )
    """,
    # 테이블당 활성 세션(ended_at IS NULL)은 최대 1개
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_active
        ON table_sessions(table_id) WHERE ended_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_sessions_table
        ON table_sessions(table_id, started_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES table_sessions(id),
        table_id INTEGER NOT NULL REFERENCES tables(id),
        client_order_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (status IN ('PENDING', 'PREPARING', 'COMPLETED')),
        total_amount INTEGER NOT NULL CHECK (total_amount > 0),
        created_at TEXT NOT NULL,
        UNIQUE (table_id, client_order_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_orders_session ON orders(session_id, id)
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        menu_id INTEGER NOT NULL,
        menu_name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 20),
        unit_price INTEGER NOT NULL CHECK (unit_price > 0)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_order_items_order ON order_items(order_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS order_history (
        order_id INTEGER PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES table_sessions(id),
        table_id INTEGER NOT NULL REFERENCES tables(id),
        client_order_id TEXT NOT NULL,
        status TEXT NOT NULL,
        total_amount INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        UNIQUE (table_id, client_order_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_history_table_completed
        ON order_history(table_id, completed_at DESC, order_id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_history_session ON order_history(session_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS order_history_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES order_history(order_id) ON DELETE CASCADE,
        menu_id INTEGER NOT NULL,
        menu_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price INTEGER NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_history_items_order ON order_history_items(order_id)
    """,
]


def _apply_order(conn: sqlite3.Connection, current_version: int | None) -> None:
    # v1: 모두 IF NOT EXISTS라 멱등. 이후 버전은 current_version 기준으로 마이그레이션을 추가한다.
    for statement in _DDL:
        conn.execute(statement)


ORDER_SCHEMA = SchemaModule(name="order", version=ORDER_SCHEMA_VERSION, apply=_apply_order)
register_schema(ORDER_SCHEMA)
