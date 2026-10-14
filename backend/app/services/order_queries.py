"""주문/이력 조회 공통 도구 (OrderService, TableService가 함께 사용).

항목(order_items)은 여러 주문을 한 번의 IN 쿼리로 가져와 조립한다 (주문마다 쿼리를 반복하지 않음).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from ..db import Database
from ..errors import NotFound
from .order_models import (
    OrderItemRecord,
    OrderRecord,
    TableSummaryRecord,
    order_number_for,
)

ORDER_SELECT = (
    "SELECT o.id, o.session_id, o.table_id, t.table_number, o.created_at, o.status, o.total_amount "
    "FROM orders o JOIN tables t ON t.id = o.table_id"
)
HISTORY_SELECT = (
    "SELECT h.order_id AS id, h.session_id, h.table_id, t.table_number, h.created_at, h.status, h.total_amount, "
    "h.completed_at FROM order_history h JOIN tables t ON t.id = h.table_id"
)


def marks(count: int) -> str:
    """IN (...) 자리표시자. 값은 항상 바인딩하고 개수만 코드에서 만든다."""
    return ",".join("?" for _ in range(count))


@contextmanager
def read_snapshot(db: Database) -> Iterator[sqlite3.Connection]:
    """한 읽기 트랜잭션(WAL 스냅샷)으로 여러 쿼리가 일관된 상태를 보게 한다. 쓰기 잠금을 잡지 않는다."""
    conn = db.connect()
    try:
        conn.execute("BEGIN")
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
    finally:
        conn.close()


def fetch_items(
    conn: sqlite3.Connection, order_ids: Sequence[int], *, history: bool = False
) -> dict[int, list[OrderItemRecord]]:
    if not order_ids:
        return {}
    table = "order_history_items" if history else "order_items"
    rows = conn.execute(
        f"SELECT order_id, menu_id, menu_name, quantity, unit_price FROM {table} "  # noqa: S608 (테이블명은 상수)
        f"WHERE order_id IN ({marks(len(order_ids))}) ORDER BY id",
        list(order_ids),
    ).fetchall()
    result: dict[int, list[OrderItemRecord]] = {}
    for r in rows:
        result.setdefault(r["order_id"], []).append(
            OrderItemRecord(
                menu_id=r["menu_id"], menu_name=r["menu_name"], quantity=r["quantity"], unit_price=r["unit_price"]
            )
        )
    return result


def to_orders(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], *, history: bool = False) -> list[OrderRecord]:
    items = fetch_items(conn, [r["id"] for r in rows], history=history)
    return [
        OrderRecord(
            id=r["id"],
            order_number=order_number_for(r["id"]),
            table_id=r["table_id"],
            table_number=r["table_number"],
            session_id=r["session_id"],
            created_at=r["created_at"],
            status=r["status"],
            total_amount=r["total_amount"],
            items=items.get(r["id"], []),
        )
        for r in rows
    ]


def find_by_client_order_id(conn: sqlite3.Connection, table_id: int, client_order_id: str) -> OrderRecord | None:
    """현재 주문 -> 이력 순으로 (table_id, client_order_id)를 찾는다 (멱등성)."""
    row = conn.execute(
        ORDER_SELECT + " WHERE o.table_id = ? AND o.client_order_id = ?", (table_id, client_order_id)
    ).fetchone()
    if row is not None:
        return to_orders(conn, [row])[0]
    row = conn.execute(
        HISTORY_SELECT + " WHERE h.table_id = ? AND h.client_order_id = ?", (table_id, client_order_id)
    ).fetchone()
    if row is not None:
        return to_orders(conn, [row], history=True)[0]
    return None


def table_summaries(
    conn: sqlite3.Connection, *, table_number: int | None = None, table_id: int | None = None, preview_limit: int | None
) -> list[TableSummaryRecord]:
    """테이블 요약 목록(번호 오름차순).

    - table_number/table_id를 주면 해당 테이블 하나만 (없으면 NotFound).
    - preview_limit: 테이블마다 최신 N건만 `orders`에 담는다. None이면 활성 세션의 전체 주문.
    - totalAmount/orderCount는 항상 활성 세션 전체 기준.
    """
    sql = "SELECT id, table_number FROM tables"
    params: list[int] = []
    if table_number is not None:
        sql += " WHERE table_number = ?"
        params.append(table_number)
    elif table_id is not None:
        sql += " WHERE id = ?"
        params.append(table_id)
    tables = conn.execute(sql + " ORDER BY table_number", params).fetchall()
    if (table_number is not None or table_id is not None) and not tables:
        raise NotFound()
    if not tables:
        return []

    table_ids = [t["id"] for t in tables]
    sessions = conn.execute(
        f"SELECT id, table_id FROM table_sessions WHERE ended_at IS NULL AND table_id IN ({marks(len(table_ids))})",
        table_ids,
    ).fetchall()
    session_of = {s["table_id"]: s["id"] for s in sessions}
    session_ids = list(session_of.values())

    totals: dict[str, tuple[int, int]] = {}
    orders_by_session: dict[str, list[OrderRecord]] = {}
    if session_ids:
        sm = marks(len(session_ids))
        for r in conn.execute(
            f"SELECT session_id, COUNT(*) AS n, COALESCE(SUM(total_amount), 0) AS total FROM orders "
            f"WHERE session_id IN ({sm}) GROUP BY session_id",
            session_ids,
        ):
            totals[r["session_id"]] = (r["n"], r["total"])
        if preview_limit is None:
            rows = conn.execute(ORDER_SELECT + f" WHERE o.session_id IN ({sm}) ORDER BY o.id DESC", session_ids).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, session_id, table_id, table_number, created_at, status, total_amount FROM ("
                "SELECT o.id, o.session_id, o.table_id, t.table_number, o.created_at, o.status, o.total_amount, "
                "ROW_NUMBER() OVER (PARTITION BY o.session_id ORDER BY o.id DESC) AS rn "
                "FROM orders o JOIN tables t ON t.id = o.table_id "
                f"WHERE o.session_id IN ({sm})) WHERE rn <= ? ORDER BY id DESC",
                [*session_ids, preview_limit],
            ).fetchall()
        for order in to_orders(conn, rows):
            orders_by_session.setdefault(order.session_id, []).append(order)

    summaries: list[TableSummaryRecord] = []
    for t in tables:
        sid = session_of.get(t["id"])
        count, total = totals.get(sid, (0, 0)) if sid else (0, 0)
        summaries.append(
            TableSummaryRecord(
                table_id=t["id"],
                table_number=t["table_number"],
                session_active=sid is not None,
                total_amount=total,
                order_count=count,
                orders=orders_by_session.get(sid, []) if sid else [],
            )
        )
    return summaries
