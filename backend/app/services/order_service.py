"""주문 생성(멱등, 서버 금액 재계산), 조회, 대시보드, 상태 전이, 삭제 (business-rules 3~6절).

- 쓰기는 모두 BEGIN IMMEDIATE 트랜잭션. 이벤트는 커밋 이후에 발행한다.
- 금액은 항상 서버가 현재 메뉴 가격으로 계산한다 (클라이언트 합계는 비교에만 사용).
"""

from __future__ import annotations

import logging
import sqlite3

from ..db import Database
from ..errors import InvalidTransition, MenuUnavailable, NotFound, PriceChanged
from ..events_port import EventPublisher, NullPublisher, ServerEvent, safe_publish
from ..schemas import OrderCreateData
from ..timeutil import Clock, utc_iso
from .menu_service import MenuService
from .order_models import (
    CreateOrderResult,
    OrderPageRecord,
    OrderRecord,
    TableSummaryRecord,
)
from .order_queries import (
    ORDER_SELECT,
    find_by_client_order_id,
    read_snapshot,
    table_summaries,
    to_orders,
)
from .table_service import TableService

logger = logging.getLogger("app.orders")

# 허용되는 상태 전이: PENDING -> PREPARING -> COMPLETED 뿐이다.
NEXT_STATUS = {"PENDING": "PREPARING", "PREPARING": "COMPLETED"}
DASHBOARD_PREVIEW = 3


class OrderService:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        menus: MenuService,
        tables: TableService,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._menus = menus
        self._tables = tables
        self._publisher: EventPublisher = publisher or NullPublisher()

    def set_publisher(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    # ---------- 생성 ----------

    def create_order(self, table_id: int, data: OrderCreateData) -> CreateOrderResult:
        # [1] 멱등 선조회: 이미 처리된 요청이면 메뉴/가격 검사 없이 기존 주문을 돌려준다
        with self._db.connection() as conn:
            existing = find_by_client_order_id(conn, table_id, data.client_order_id)
        if existing is not None:
            return CreateOrderResult(existing, created=False)

        # [2] 판매 가능 여부와 가격 재계산 (쓰기 잠금 밖의 별도 읽기)
        menu_ids = [menu_id for menu_id, _ in data.items]
        menus = self._menus.get_active_menus_by_ids(menu_ids)
        missing = [menu_id for menu_id in menu_ids if menu_id not in menus]
        if missing:
            raise MenuUnavailable(missing)
        total = sum(menus[menu_id].price * quantity for menu_id, quantity in data.items)
        if total != data.client_total:
            raise PriceChanged([{"menuId": menu_id, "price": menus[menu_id].price} for menu_id in menu_ids])

        # [3] 저장: 재확인 -> 세션 확보 -> 주문/항목 INSERT
        now = utc_iso(self._clock())
        try:
            with self._db.transaction() as conn:
                existing = find_by_client_order_id(conn, table_id, data.client_order_id)
                if existing is not None:
                    return CreateOrderResult(existing, created=False)
                session_id = self._tables.ensure_active_session(conn, table_id, now)
                cur = conn.execute(
                    "INSERT INTO orders(session_id, table_id, client_order_id, status, total_amount, created_at) "
                    "VALUES (?, ?, ?, 'PENDING', ?, ?)",
                    (session_id, table_id, data.client_order_id, total, now),
                )
                order_id = int(cur.lastrowid)
                conn.executemany(
                    "INSERT INTO order_items(order_id, menu_id, menu_name, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                    [
                        (order_id, menu_id, menus[menu_id].name, quantity, menus[menu_id].price)
                        for menu_id, quantity in data.items
                    ],
                )
                order = self._load(conn, order_id)
        except sqlite3.IntegrityError:
            # 동시에 같은 clientOrderId가 먼저 저장된 경우(UNIQUE 위반): 그 주문을 돌려준다
            with self._db.connection() as conn:
                existing = find_by_client_order_id(conn, table_id, data.client_order_id)
            if existing is not None:
                return CreateOrderResult(existing, created=False)
            raise

        safe_publish(
            self._publisher,
            ServerEvent(type="order_created", table_id=table_id, payload={"orderId": order.id}),
        )
        return CreateOrderResult(order, created=True)

    # ---------- 조회 ----------

    def list_session_orders(self, table_id: int, page: int, size: int) -> OrderPageRecord:
        """고객의 현재 세션 주문(최신순). 활성 세션이 없으면 빈 페이지."""
        with self._db.connection() as conn:
            session = conn.execute(
                "SELECT id FROM table_sessions WHERE table_id = ? AND ended_at IS NULL", (table_id,)
            ).fetchone()
            if session is None:
                return OrderPageRecord(items=[], page=page, size=size, has_next=False)
            rows = conn.execute(
                ORDER_SELECT + " WHERE o.session_id = ? ORDER BY o.id DESC LIMIT ? OFFSET ?",
                (session["id"], size + 1, page * size),
            ).fetchall()
            has_next = len(rows) > size
            orders = to_orders(conn, rows[:size])
        return OrderPageRecord(items=orders, page=page, size=size, has_next=has_next)

    def dashboard(self, table_number: int | None = None) -> list[TableSummaryRecord]:
        """모든 테이블(번호 오름차순)의 요약. table_number를 주면 그 테이블의 현재 세션 전체 주문."""
        with read_snapshot(self._db) as conn:
            return table_summaries(
                conn,
                table_number=table_number,
                preview_limit=None if table_number is not None else DASHBOARD_PREVIEW,
            )

    def get_order(self, order_id: int) -> OrderRecord:
        with self._db.connection() as conn:
            return self._load(conn, order_id)

    # ---------- 변경 ----------

    def change_status(self, order_id: int, new_status: str) -> OrderRecord:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT table_id, status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise NotFound()
            current = row["status"]
            if NEXT_STATUS.get(current) != new_status:
                raise InvalidTransition(current, new_status)
            changed = conn.execute(
                "UPDATE orders SET status = ? WHERE id = ? AND status = ?", (new_status, order_id, current)
            ).rowcount
            if changed != 1:  # 방어적 확인 (BEGIN IMMEDIATE 아래에서는 발생하지 않는다)
                raise InvalidTransition(current, new_status)
            order = self._load(conn, order_id)
            table_id = row["table_id"]
        safe_publish(
            self._publisher,
            ServerEvent(
                type="order_status_changed", table_id=table_id, payload={"orderId": order_id, "status": new_status}
            ),
        )
        return order

    def delete_order(self, order_id: int) -> TableSummaryRecord:
        """활성 세션의 주문을 삭제하고 갱신된 테이블 요약(최신 3건)을 돌려준다."""
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT table_id, status, total_amount FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row is None:
                raise NotFound()
            conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))  # order_items는 CASCADE
            summary = table_summaries(conn, table_id=row["table_id"], preview_limit=DASHBOARD_PREVIEW)[0]
            table_id = row["table_id"]
            status, amount = row["status"], row["total_amount"]
        logger.info("order deleted id=%s table=%s status=%s amount=%s", order_id, table_id, status, amount)
        safe_publish(
            self._publisher,
            ServerEvent(type="order_deleted", table_id=table_id, payload={"orderId": order_id}),
        )
        return summary

    # ---------- 내부 ----------

    @staticmethod
    def _load(conn: sqlite3.Connection, order_id: int) -> OrderRecord:
        row = conn.execute(ORDER_SELECT + " WHERE o.id = ?", (order_id,)).fetchone()
        if row is None:
            raise NotFound()
        return to_orders(conn, [row])[0]
