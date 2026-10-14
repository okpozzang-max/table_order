from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.deps import AppContainer
from app.errors import DuplicateTable, NoActiveSession, NotFound
from tests.order_helpers import place, table_id_of


def utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


class TestRegisterAndList:
    def test_register_returns_info_without_session(self, seeded: AppContainer) -> None:
        info = seeded.tables.register(6, "4321")
        assert (info.table_number, info.session_active) == (6, False)
        assert info.id > 0

    def test_registered_table_can_log_in_immediately(self, seeded: AppContainer) -> None:
        seeded.tables.register(6, "4321")
        result = seeded.auth.login_table("demo", 6, "4321")
        assert result.table_number == 6

    def test_password_is_stored_as_bcrypt_hash(self, seeded: AppContainer) -> None:
        seeded.tables.register(6, "4321")
        with seeded.db.connection() as conn:
            stored = conn.execute("SELECT password_hash FROM tables WHERE table_number = 6").fetchone()[0]
        assert stored.startswith("$2") and "4321" not in stored

    def test_duplicate_number_rejected(self, seeded: AppContainer) -> None:
        with pytest.raises(DuplicateTable):
            seeded.tables.register(3, "1111")

    def test_list_is_sorted_and_reflects_active_session(self, seeded: AppContainer) -> None:
        seeded.tables.register(10, "1111")
        seeded.tables.register(6, "1111")
        place(seeded, table_id_of(seeded, 2))
        tables = seeded.tables.list_tables()
        assert [t.table_number for t in tables] == [1, 2, 3, 4, 5, 6, 10]
        assert {t.table_number for t in tables if t.session_active} == {2}


class TestSessions:
    def test_ensure_active_session_is_stable_and_well_formed(self, seeded: AppContainer) -> None:
        tid = table_id_of(seeded, 1)
        with seeded.db.transaction() as conn:
            first = seeded.tables.ensure_active_session(conn, tid, "2026-10-14T00:00:00Z")
            second = seeded.tables.ensure_active_session(conn, tid, "2026-10-14T00:00:01Z")
        assert first == second
        assert re.fullmatch(r"sess_[0-9a-f]{12}", first)

    def test_sessions_are_per_table_and_new_after_end(self, seeded: AppContainer) -> None:
        a, b = table_id_of(seeded, 1), table_id_of(seeded, 2)
        s1 = place(seeded, a).order.session_id
        s2 = place(seeded, b).order.session_id
        assert s1 != s2
        seeded.tables.end_session(a)
        s3 = place(seeded, a).order.session_id
        assert s3 not in (s1, s2)

    def test_session_id_collision_is_retried(self, seeded: AppContainer, monkeypatch: pytest.MonkeyPatch) -> None:
        tid = table_id_of(seeded, 1)
        with seeded.db.transaction() as conn:
            conn.execute("INSERT INTO table_sessions(id, table_id, started_at, ended_at) VALUES ('sess_000000000001', ?, 't', 't')", (tid,))
        values = iter(["000000000001", "000000000002"])
        monkeypatch.setattr("app.services.table_service.secrets.token_hex", lambda _n: next(values))
        with seeded.db.transaction() as conn:
            assert seeded.tables.ensure_active_session(conn, tid, "t") == "sess_000000000002"


class TestEndSession:
    def test_archives_orders_keeping_ids_numbers_items_and_status(self, seeded: AppContainer, clock) -> None:  # type: ignore[no-untyped-def]
        tid = table_id_of(seeded, 3)
        o1 = place(seeded, tid, [(1, 2), (6, 1)]).order
        o2 = place(seeded, tid, [(8, 3)]).order
        seeded.orders.change_status(o1.id, "PREPARING")
        clock.advance(3600)

        summary = seeded.tables.end_session(tid)

        assert summary.table_id == tid
        assert summary.archived_order_count == 2
        assert summary.archived_total_amount == o1.total_amount + o2.total_amount == 19000 + 6000
        history = seeded.tables.get_history(tid)
        assert [h.order_id for h in history] == [o2.id, o1.id]
        assert [h.order_number for h in history] == [o2.order_number, o1.order_number]
        by_id = {h.order_id: h for h in history}
        assert [(i.menu_name, i.quantity, i.unit_price) for i in by_id[o1.id].items] == [("김치찌개", 2, 9000), ("공기밥", 1, 1000)]
        assert by_id[o1.id].created_at == o1.created_at
        assert all(h.completed_at == summary.ended_at for h in history)
        with seeded.db.connection() as conn:
            statuses = {r["order_id"]: r["status"] for r in conn.execute("SELECT order_id, status FROM order_history")}
            assert statuses == {o1.id: "PREPARING", o2.id: "PENDING"}  # 상태 보존
            assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 0

    def test_after_end_current_views_are_empty(self, seeded: AppContainer) -> None:
        tid = table_id_of(seeded, 3)
        place(seeded, tid)
        seeded.tables.end_session(tid)
        summary = seeded.orders.dashboard(3)[0]
        assert (summary.session_active, summary.total_amount, summary.order_count, summary.orders) == (False, 0, 0, [])
        assert seeded.orders.list_session_orders(tid, 0, 10).items == []

    def test_empty_active_session_can_be_ended(self, seeded: AppContainer) -> None:
        tid = table_id_of(seeded, 3)
        order = place(seeded, tid).order
        seeded.orders.delete_order(order.id)  # 세션은 남는다
        summary = seeded.tables.end_session(tid)
        assert (summary.archived_order_count, summary.archived_total_amount) == (0, 0)

    def test_second_end_raises_no_active_session(self, seeded: AppContainer) -> None:
        tid = table_id_of(seeded, 3)
        place(seeded, tid)
        seeded.tables.end_session(tid)
        with pytest.raises(NoActiveSession):
            seeded.tables.end_session(tid)

    def test_never_ordered_table_has_no_session(self, seeded: AppContainer) -> None:
        with pytest.raises(NoActiveSession):
            seeded.tables.end_session(table_id_of(seeded, 4))

    def test_unknown_table(self, seeded: AppContainer) -> None:
        with pytest.raises(NotFound):
            seeded.tables.end_session(9999)

    def test_only_target_table_is_affected(self, seeded: AppContainer) -> None:
        a, b = table_id_of(seeded, 1), table_id_of(seeded, 2)
        place(seeded, a)
        kept = place(seeded, b).order
        seeded.tables.end_session(a)
        assert [o.id for o in seeded.orders.list_session_orders(b, 0, 10).items] == [kept.id]

    def test_failure_during_archive_rolls_everything_back(self, seeded: AppContainer) -> None:
        tid = table_id_of(seeded, 3)
        order = place(seeded, tid, [(1, 1), (2, 1)]).order
        with seeded.db.transaction() as conn:  # 항목 복사 단계에서 실패하도록 함정을 둔다
            conn.execute(
                "CREATE TRIGGER fail_items BEFORE INSERT ON order_history_items "
                "BEGIN SELECT RAISE(ABORT, 'boom'); END"
            )
        with pytest.raises(sqlite3.DatabaseError):
            seeded.tables.end_session(tid)
        with seeded.db.connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM order_history").fetchone()[0] == 0
            assert conn.execute("SELECT ended_at FROM table_sessions").fetchone()[0] is None
        assert [o.id for o in seeded.orders.list_session_orders(tid, 0, 10).items] == [order.id]
        assert seeded.orders.get_order(order.id).total_amount == 9000 + 8500

    def test_event_published_after_commit_with_count(self, seeded: AppContainer, publisher) -> None:  # type: ignore[no-untyped-def]
        tid = table_id_of(seeded, 3)
        place(seeded, tid)
        place(seeded, tid)
        publisher.events.clear()
        seeded.tables.end_session(tid)
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [
            ("session_ended", tid, {"archivedOrderCount": 2})
        ]

    def test_no_event_when_no_session(self, seeded: AppContainer, publisher) -> None:  # type: ignore[no-untyped-def]
        publisher.events.clear()
        with pytest.raises(NoActiveSession):
            seeded.tables.end_session(table_id_of(seeded, 4))
        assert publisher.events == []


class TestHistory:
    def _end_at(self, seeded: AppContainer, clock, table_number: int, when: datetime) -> int:  # type: ignore[no-untyped-def]
        tid = table_id_of(seeded, table_number)
        clock.now = when
        order = place(seeded, tid).order
        seeded.tables.end_session(tid)
        return order.id

    def test_ordering_is_newest_first_then_id_desc(self, seeded: AppContainer, clock) -> None:  # type: ignore[no-untyped-def]
        tid = table_id_of(seeded, 1)
        clock.now = utc(2026, 10, 14, 1)
        a = place(seeded, tid).order.id
        b = place(seeded, tid).order.id
        seeded.tables.end_session(tid)  # a, b 동시 완료 -> id 내림차순
        clock.now = utc(2026, 10, 14, 5)
        c = place(seeded, tid).order.id
        seeded.tables.end_session(tid)
        assert [h.order_id for h in seeded.tables.get_history(tid)] == [c, b, a]

    def test_only_requested_table(self, seeded: AppContainer, clock) -> None:  # type: ignore[no-untyped-def]
        mine = self._end_at(seeded, clock, 1, utc(2026, 10, 14, 1))
        self._end_at(seeded, clock, 2, utc(2026, 10, 14, 2))
        assert [h.order_id for h in seeded.tables.get_history(table_id_of(seeded, 1))] == [mine]

    def test_date_boundaries_use_seoul_midnight(self, seeded: AppContainer, clock) -> None:  # type: ignore[no-untyped-def]
        tid = table_id_of(seeded, 1)
        # 10-14 23:59:59 KST = 10-14 14:59:59Z / 10-15 00:00:00 KST = 10-14 15:00:00Z
        before = self._end_at(seeded, clock, 1, utc(2026, 10, 14, 14, 59, 59))
        after = self._end_at(seeded, clock, 1, utc(2026, 10, 14, 15, 0, 0))
        ids = lambda **kw: [h.order_id for h in seeded.tables.get_history(tid, **kw)]  # noqa: E731
        assert ids(from_date=date(2026, 10, 15)) == [after]
        assert ids(to_date=date(2026, 10, 14)) == [before]
        assert ids(from_date=date(2026, 10, 14), to_date=date(2026, 10, 14)) == [before]
        assert ids(from_date=date(2026, 10, 15), to_date=date(2026, 10, 15)) == [after]
        assert ids(from_date=date(2026, 10, 14), to_date=date(2026, 10, 15)) == [after, before]
        assert ids(from_date=date(2026, 10, 16)) == []
        assert ids(to_date=date(2026, 10, 13)) == []
        assert ids() == [after, before]

    def test_unknown_table(self, seeded: AppContainer) -> None:
        with pytest.raises(NotFound):
            seeded.tables.get_history(9999)

    def test_table_without_history_returns_empty(self, seeded: AppContainer) -> None:
        assert seeded.tables.get_history(table_id_of(seeded, 5)) == []
