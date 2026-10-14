"""메뉴 조회/등록/수정/소프트 삭제/순서 변경 (business-rules 3절).

- 삭제는 deleted_at 표시(소프트). 조회·검증·순서 계산은 활성 메뉴(deleted_at IS NULL)만 대상으로 한다.
- 카테고리는 별도 테이블 없이 문자열이며, 메뉴마다 category_order(처음 만들어진 순서)를 저장해 안정적으로 유지한다.
- 이벤트(menu_changed)는 커밋 이후에 발행한다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from ..db import Database
from ..errors import NotFound, ValidationFailed
from ..events_port import EventPublisher, NullPublisher, ServerEvent, safe_publish
from ..schemas import MSG_DUPLICATE_NAME, MSG_ORDERED_IDS, MenuData
from ..timeutil import Clock, utc_iso

_SELECT = (
    "SELECT id, name, price, description, category, category_order, display_order, image_url "
    "FROM menus"
)


@dataclass(frozen=True)
class MenuRecord:
    id: int
    name: str
    price: int
    description: str
    category: str
    image_url: str | None
    display_order: int


@dataclass(frozen=True)
class CategoryMenus:
    category: str
    menus: list[MenuRecord]


def _record(row: sqlite3.Row) -> MenuRecord:
    return MenuRecord(
        id=row["id"],
        name=row["name"],
        price=row["price"],
        description=row["description"],
        category=row["category"],
        image_url=row["image_url"],
        display_order=row["display_order"],
    )


class MenuService:
    def __init__(self, *, db: Database, clock: Clock, publisher: EventPublisher | None = None) -> None:
        self._db = db
        self._clock = clock
        self._publisher: EventPublisher = publisher or NullPublisher()

    def set_publisher(self, publisher: EventPublisher) -> None:
        """backend-order가 실제 EventBroker를 연결할 때 사용한다."""
        self._publisher = publisher

    # ---------- 조회 ----------

    def list_grouped(self) -> list[CategoryMenus]:
        with self._db.connection() as conn:
            rows = conn.execute(
                _SELECT + " WHERE deleted_at IS NULL ORDER BY category_order, display_order, id"
            ).fetchall()
        groups: dict[str, list[MenuRecord]] = {}
        for row in rows:
            groups.setdefault(row["category"], []).append(_record(row))
        return [CategoryMenus(category=c, menus=m) for c, m in groups.items()]

    def get_active_menus_by_ids(self, ids: list[int]) -> dict[int, MenuRecord]:
        """삭제되지 않은 메뉴만 반환한다 (주문 생성 시 가격 재계산/판매 가능 여부 판단용)."""
        unique = sorted(set(ids))
        if not unique:
            return {}
        marks = ",".join("?" for _ in unique)
        with self._db.connection() as conn:
            rows = conn.execute(
                _SELECT + f" WHERE deleted_at IS NULL AND id IN ({marks})", unique
            ).fetchall()
        return {r["id"]: _record(r) for r in rows}

    # ---------- 변경 ----------

    def create(self, data: MenuData) -> MenuRecord:
        now = utc_iso(self._clock())
        try:
            with self._db.transaction() as conn:
                self._ensure_unique_name(conn, data.category, data.name, exclude_id=None)
                category_order = self._category_order_for(conn, data.category)
                display_order = self._next_display_order(conn, data.category)
                cur = conn.execute(
                    "INSERT INTO menus(name, price, description, category, category_order, display_order, "
                    "image_url, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        data.name,
                        data.price,
                        data.description,
                        data.category,
                        category_order,
                        display_order,
                        data.image_url,
                        now,
                        now,
                    ),
                )
                record = self._get_active(conn, int(cur.lastrowid))
        except sqlite3.IntegrityError:
            raise ValidationFailed({"name": MSG_DUPLICATE_NAME}) from None
        self._notify()
        return record

    def update(self, menu_id: int, data: MenuData) -> MenuRecord:
        now = utc_iso(self._clock())
        try:
            with self._db.transaction() as conn:
                current = conn.execute(
                    "SELECT category FROM menus WHERE id = ? AND deleted_at IS NULL", (menu_id,)
                ).fetchone()
                if current is None:
                    raise NotFound()
                self._ensure_unique_name(conn, data.category, data.name, exclude_id=menu_id)
                old_category = current["category"]
                if data.category != old_category:
                    category_order = self._category_order_for(conn, data.category)
                    display_order = self._next_display_order(conn, data.category)
                    conn.execute(
                        "UPDATE menus SET name = ?, price = ?, description = ?, category = ?, category_order = ?, "
                        "display_order = ?, image_url = ?, updated_at = ? WHERE id = ?",
                        (
                            data.name,
                            data.price,
                            data.description,
                            data.category,
                            category_order,
                            display_order,
                            data.image_url,
                            now,
                            menu_id,
                        ),
                    )
                    self._renumber(conn, old_category)
                else:
                    conn.execute(
                        "UPDATE menus SET name = ?, price = ?, description = ?, image_url = ?, updated_at = ? "
                        "WHERE id = ?",
                        (data.name, data.price, data.description, data.image_url, now, menu_id),
                    )
                record = self._get_active(conn, menu_id)
        except sqlite3.IntegrityError:
            raise ValidationFailed({"name": MSG_DUPLICATE_NAME}) from None
        self._notify()
        return record

    def delete(self, menu_id: int) -> None:
        now = utc_iso(self._clock())
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT category FROM menus WHERE id = ? AND deleted_at IS NULL", (menu_id,)
            ).fetchone()
            if row is None:
                raise NotFound()
            conn.execute("UPDATE menus SET deleted_at = ?, updated_at = ? WHERE id = ?", (now, now, menu_id))
            self._renumber(conn, row["category"])
        self._notify()

    def reorder(self, category: str, ordered_ids: list[int]) -> None:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT id FROM menus WHERE category = ? AND deleted_at IS NULL", (category,)
            ).fetchall()
            if not rows:
                raise NotFound()
            active = {r["id"] for r in rows}
            if len(ordered_ids) != len(active) or set(ordered_ids) != active:
                raise ValidationFailed({"orderedIds": MSG_ORDERED_IDS})
            for position, menu_id in enumerate(ordered_ids, start=1):
                conn.execute("UPDATE menus SET display_order = ? WHERE id = ?", (position, menu_id))
        self._notify()

    # ---------- 내부 ----------

    def _notify(self) -> None:
        safe_publish(self._publisher, ServerEvent(type="menu_changed"))

    def _get_active(self, conn: sqlite3.Connection, menu_id: int) -> MenuRecord:
        row = conn.execute(_SELECT + " WHERE id = ? AND deleted_at IS NULL", (menu_id,)).fetchone()
        if row is None:
            raise NotFound()
        return _record(row)

    def _ensure_unique_name(
        self, conn: sqlite3.Connection, category: str, name: str, *, exclude_id: int | None
    ) -> None:
        params: list[Any] = [category, name]
        sql = "SELECT 1 FROM menus WHERE category = ? AND name = ? AND deleted_at IS NULL"
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        if conn.execute(sql, params).fetchone():
            raise ValidationFailed({"name": MSG_DUPLICATE_NAME})

    def _category_order_for(self, conn: sqlite3.Connection, category: str) -> int:
        row = conn.execute(
            "SELECT category_order FROM menus WHERE category = ? AND deleted_at IS NULL LIMIT 1", (category,)
        ).fetchone()
        if row is not None:
            return int(row["category_order"])
        row = conn.execute("SELECT COALESCE(MAX(category_order), 0) + 1 AS n FROM menus WHERE deleted_at IS NULL").fetchone()
        return int(row["n"])

    def _next_display_order(self, conn: sqlite3.Connection, category: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(display_order), 0) + 1 AS n FROM menus WHERE category = ? AND deleted_at IS NULL",
            (category,),
        ).fetchone()
        return int(row["n"])

    def _renumber(self, conn: sqlite3.Connection, category: str) -> None:
        rows = conn.execute(
            "SELECT id FROM menus WHERE category = ? AND deleted_at IS NULL ORDER BY display_order, id", (category,)
        ).fetchall()
        for position, row in enumerate(rows, start=1):
            conn.execute("UPDATE menus SET display_order = ? WHERE id = ?", (position, row["id"]))
