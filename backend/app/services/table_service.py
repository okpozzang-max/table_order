"""테이블 등록/목록, 세션 시작·종료(이용 완료), 이력 이관, 과거 내역 조회 (business-rules 5.2, 6.3, 7절).

- 이벤트(session_ended)는 커밋 이후에 발행한다.
- 이용 완료는 한 트랜잭션: 주문/항목을 이력으로 복사 -> 현재 주문 삭제 -> 세션 종료. 중간에 실패하면 전부 롤백.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..db import Database
from ..errors import DuplicateTable, NoActiveSession, NotFound
from ..events_port import EventPublisher, NullPublisher, ServerEvent, safe_publish
from ..security import hash_password
from ..timeutil import Clock, utc_iso
from .order_models import (
    HistoryOrderRecord,
    SessionSummaryRecord,
    TableInfoRecord,
    order_number_for,
)
from .order_queries import HISTORY_SELECT, fetch_items


class TableService:
    def __init__(
        self,
        *,
        db: Database,
        clock: Clock,
        bcrypt_rounds: int,
        timezone: str,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._bcrypt_rounds = bcrypt_rounds
        self._tz = ZoneInfo(timezone)
        self._publisher: EventPublisher = publisher or NullPublisher()

    def set_publisher(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    # ---------- 등록 / 목록 ----------

    def register(self, table_number: int, password: str) -> TableInfoRecord:
        password_hash = hash_password(password, self._bcrypt_rounds)  # 쓰기 잠금 밖에서 계산 (수백 ms)
        now = utc_iso(self._clock())
        try:
            with self._db.transaction() as conn:
                cur = conn.execute(
                    "INSERT INTO tables(table_number, password_hash, created_at) VALUES (?, ?, ?)",
                    (table_number, password_hash, now),
                )
                table_id = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            raise DuplicateTable(table_number) from None
        return TableInfoRecord(id=table_id, table_number=table_number, session_active=False)

    def list_tables(self) -> list[TableInfoRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT t.id, t.table_number, "
                "EXISTS (SELECT 1 FROM table_sessions s WHERE s.table_id = t.id AND s.ended_at IS NULL) AS active "
                "FROM tables t ORDER BY t.table_number"
            ).fetchall()
        return [TableInfoRecord(id=r["id"], table_number=r["table_number"], session_active=bool(r["active"])) for r in rows]

    # ---------- 세션 ----------

    def ensure_active_session(self, conn: sqlite3.Connection, table_id: int, now: str) -> str:
        """활성 세션 ID를 돌려준다. 없으면 만든다. 호출자의 쓰기 트랜잭션 안에서 사용한다."""
        existing = self._active_session_id(conn, table_id)
        if existing is not None:
            return existing
        for _ in range(3):
            session_id = "sess_" + secrets.token_hex(6)
            try:
                conn.execute(
                    "INSERT INTO table_sessions(id, table_id, started_at) VALUES (?, ?, ?)",
                    (session_id, table_id, now),
                )
                return session_id
            except sqlite3.IntegrityError:
                # 세션 ID 충돌(PK) 또는 그 사이에 생긴 활성 세션(부분 유니크). 후자면 그것을 사용한다.
                existing = self._active_session_id(conn, table_id)
                if existing is not None:
                    return existing
        raise RuntimeError("세션 ID를 만들지 못했어요")

    @staticmethod
    def _active_session_id(conn: sqlite3.Connection, table_id: int) -> str | None:
        row = conn.execute(
            "SELECT id FROM table_sessions WHERE table_id = ? AND ended_at IS NULL", (table_id,)
        ).fetchone()
        return row["id"] if row else None

    def end_session(self, table_id: int) -> SessionSummaryRecord:
        now = utc_iso(self._clock())
        with self._db.transaction() as conn:
            if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
                raise NotFound()
            session_id = self._active_session_id(conn, table_id)
            if session_id is None:
                raise NoActiveSession()

            before = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(total_amount), 0) AS total FROM orders WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            count, total = int(before["n"]), int(before["total"])
            item_count = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE session_id = ?)",
                    (session_id,),
                ).fetchone()["n"]
            )

            copied = conn.execute(
                "INSERT INTO order_history(order_id, session_id, table_id, client_order_id, status, total_amount, "
                "created_at, completed_at) "
                "SELECT id, session_id, table_id, client_order_id, status, total_amount, created_at, ? "
                "FROM orders WHERE session_id = ? ORDER BY id",
                (now, session_id),
            ).rowcount
            copied_items = conn.execute(
                "INSERT INTO order_history_items(order_id, menu_id, menu_name, quantity, unit_price) "
                "SELECT oi.order_id, oi.menu_id, oi.menu_name, oi.quantity, oi.unit_price "
                "FROM order_items oi JOIN orders o ON o.id = oi.order_id "
                "WHERE o.session_id = ? ORDER BY oi.id",
                (session_id,),
            ).rowcount
            deleted = conn.execute("DELETE FROM orders WHERE session_id = ?", (session_id,)).rowcount
            if copied != count or deleted != count or copied_items != item_count:
                # 데이터 유실 방지: 이관/삭제 수가 어긋나면 예외로 전체 롤백한다
                raise RuntimeError("이력 이관 결과가 일치하지 않아요")
            conn.execute("UPDATE table_sessions SET ended_at = ? WHERE id = ?", (now, session_id))

        safe_publish(
            self._publisher,
            ServerEvent(type="session_ended", table_id=table_id, payload={"archivedOrderCount": count}),
        )
        return SessionSummaryRecord(
            table_id=table_id, ended_at=now, archived_order_count=count, archived_total_amount=total
        )

    # ---------- 과거 내역 ----------

    def get_history(
        self, table_id: int, from_date: date | None = None, to_date: date | None = None
    ) -> list[HistoryOrderRecord]:
        """이용 완료일(`TIMEZONE` 기준 날짜) 포함 구간의 이력. completed_at 내림차순, 같으면 주문 ID 내림차순."""
        sql = HISTORY_SELECT + " WHERE h.table_id = ?"
        params: list[object] = [table_id]
        if from_date is not None:
            sql += " AND h.completed_at >= ?"
            params.append(self._local_midnight_utc(from_date))
        if to_date is not None and to_date < date.max:
            sql += " AND h.completed_at < ?"
            params.append(self._local_midnight_utc(to_date + timedelta(days=1)))
        sql += " ORDER BY h.completed_at DESC, h.order_id DESC"

        with self._db.connection() as conn:
            if conn.execute("SELECT 1 FROM tables WHERE id = ?", (table_id,)).fetchone() is None:
                raise NotFound()
            rows = conn.execute(sql, params).fetchall()
            items = fetch_items(conn, [r["id"] for r in rows], history=True)
        return [
            HistoryOrderRecord(
                order_id=r["id"],
                order_number=order_number_for(r["id"]),
                table_number=r["table_number"],
                created_at=r["created_at"],
                items=items.get(r["id"], []),
                total_amount=r["total_amount"],
                completed_at=r["completed_at"],
            )
            for r in rows
        ]

    def _local_midnight_utc(self, day: date) -> str:
        return utc_iso(datetime.combine(day, time.min, tzinfo=self._tz))
