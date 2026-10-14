"""core 모듈 스키마: menus, tables, login_attempts. (주문/세션/이력 테이블은 backend-order 모듈)"""

from __future__ import annotations

import sqlite3

from .db import SchemaModule, register_schema

CORE_SCHEMA_VERSION = 1

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL CHECK (price BETWEEN 100 AND 1000000),
        description TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL,
        category_order INTEGER NOT NULL,
        display_order INTEGER NOT NULL,
        image_url TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_menus_category_name
        ON menus(category, name) WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_menus_active_order
        ON menus(category_order, display_order) WHERE deleted_at IS NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_number INTEGER NOT NULL UNIQUE CHECK (table_number BETWEEN 1 AND 999),
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS login_attempts (
        scope TEXT NOT NULL,
        key TEXT NOT NULL,
        failure_count INTEGER NOT NULL DEFAULT 0,
        locked_until TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (scope, key)
    )
    """,
]


def _apply_core(conn: sqlite3.Connection, current_version: int | None) -> None:
    # v1: 모두 IF NOT EXISTS라 멱등. 이후 버전은 current_version 기준으로 마이그레이션을 추가한다.
    for statement in _DDL:
        conn.execute(statement)


CORE_SCHEMA = SchemaModule(name="core", version=CORE_SCHEMA_VERSION, apply=_apply_core)
register_schema(CORE_SCHEMA)
