from __future__ import annotations

import threading

import pytest

from app.deps import AppContainer
from app.errors import InvalidTransition, MenuUnavailable, NotFound, PriceChanged
from app.schemas import MenuData
from tests.order_helpers import PRICES, make_order_data, place, table_id_of

CID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def t1(seeded: AppContainer) -> int:
    return table_id_of(seeded, 1)


def menu_data(seeded: AppContainer, menu_id: int, **changes: object) -> MenuData:
    m = seeded.menus.get_active_menus_by_ids([menu_id])[menu_id]
    values = dict(name=m.name, price=m.price, description=m.description, category=m.category, image_url=m.image_url)
    values.update(changes)
    return MenuData(**values)  # type: ignore[arg-type]


class TestCreate:
    def test_recalculates_total_and_snapshots_items(self, seeded: AppContainer, t1: int) -> None:
        result = place(seeded, t1, [(1, 2), (6, 3)])
        order = result.order
        assert result.created is True
        assert order.total_amount == 9000 * 2 + 1000 * 3
        assert order.status == "PENDING"
        assert order.table_number == 1 and order.table_id == t1
        assert order.order_number == str(order.id).zfill(4)
        assert [(i.menu_id, i.menu_name, i.quantity, i.unit_price) for i in order.items] == [
            (1, "김치찌개", 2, 9000),
            (6, "공기밥", 3, 1000),
        ]

    def test_existing_orders_keep_snapshot_after_menu_change_or_delete(self, seeded: AppContainer, t1: int) -> None:
        order = place(seeded, t1, [(1, 1), (2, 1)]).order
        seeded.menus.update(1, menu_data(seeded, 1, price=12345, name="김치찌개 특"))
        seeded.menus.delete(2)
        loaded = seeded.orders.get_order(order.id)
        assert loaded.total_amount == 17500
        assert [(i.menu_name, i.unit_price) for i in loaded.items] == [("김치찌개", 9000), ("된장찌개", 8500)]

    def test_first_order_creates_session_and_later_orders_reuse_it(self, seeded: AppContainer, t1: int) -> None:
        assert seeded.tables.list_tables()[0].session_active is False
        first, second = place(seeded, t1).order, place(seeded, t1).order
        assert first.session_id == second.session_id
        assert seeded.tables.list_tables()[0].session_active is True

    def test_event_published_once_with_order_id(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        publisher.events.clear()
        order = place(seeded, t1).order
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [("order_created", t1, {"orderId": order.id})]

    # ----- 멱등성 -----

    def test_same_client_order_id_returns_existing_without_new_event(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        first = place(seeded, t1, [(1, 1)], client_order_id=CID)
        publisher.events.clear()
        again = place(seeded, t1, [(1, 1)], client_order_id=CID)
        assert (first.created, again.created) == (True, False)
        assert again.order == first.order
        assert publisher.events == []
        assert len(seeded.orders.list_session_orders(t1, 0, 50).items) == 1

    def test_replay_ignores_body_differences(self, seeded: AppContainer, t1: int) -> None:
        first = place(seeded, t1, [(1, 1)], client_order_id=CID)
        again = place(seeded, t1, [(2, 5)], client_order_id=CID)
        assert again.created is False and again.order.id == first.order.id and again.order.total_amount == 9000

    def test_replay_wins_over_menu_and_price_validation(self, seeded: AppContainer, t1: int) -> None:
        first = place(seeded, t1, [(1, 1)], client_order_id=CID)
        seeded.menus.delete(1)
        again = place(seeded, t1, [(1, 1)], client_order_id=CID)
        assert again.created is False and again.order.id == first.order.id

    def test_same_key_on_other_table_is_independent(self, seeded: AppContainer, t1: int) -> None:
        t2 = table_id_of(seeded, 2)
        a = place(seeded, t1, client_order_id=CID)
        b = place(seeded, t2, client_order_id=CID)
        assert a.created and b.created and a.order.id != b.order.id

    def test_replay_after_end_session_returns_archived_order_not_a_duplicate(self, seeded: AppContainer, t1: int) -> None:
        first = place(seeded, t1, client_order_id=CID)
        seeded.tables.end_session(t1)
        again = place(seeded, t1, client_order_id=CID)
        assert again.created is False
        assert again.order.id == first.order.id and again.order.session_id == first.order.session_id
        assert seeded.orders.list_session_orders(t1, 0, 10).items == []  # 새 세션을 만들지 않았다
        assert seeded.tables.list_tables()[0].session_active is False

    def test_deleted_order_key_can_be_reused(self, seeded: AppContainer, t1: int) -> None:
        first = place(seeded, t1, client_order_id=CID).order
        seeded.orders.delete_order(first.id)
        again = place(seeded, t1, client_order_id=CID)
        assert again.created is True and again.order.id != first.id

    def test_concurrent_same_key_creates_exactly_one_order(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        publisher.events.clear()
        data = make_order_data([(1, 1)], client_order_id=CID)
        results: list = []
        barrier = threading.Barrier(6)

        def worker() -> None:
            barrier.wait()
            results.append(seeded.orders.create_order(t1, data))

        threads = [threading.Thread(target=worker) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(results) == 6
        assert sum(r.created for r in results) == 1
        assert len({r.order.id for r in results}) == 1
        assert len(seeded.orders.list_session_orders(t1, 0, 50).items) == 1
        assert [e.type for e in publisher.events] == ["order_created"]

    # ----- 메뉴/가격 -----

    def test_unavailable_menus_listed_and_nothing_saved(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        seeded.menus.delete(3)
        publisher.events.clear()
        with pytest.raises(MenuUnavailable) as exc:
            seeded.orders.create_order(t1, make_order_data([(1, 1), (3, 1), (999, 1), (500, 2)], client_total=1))
        assert exc.value.menu_ids == [3, 500, 999]
        assert exc.value.to_body()["details"] == {"menuIds": [3, 500, 999]}
        assert seeded.orders.list_session_orders(t1, 0, 10).items == []
        assert seeded.tables.list_tables()[0].session_active is False  # 세션도 만들지 않는다
        assert publisher.events == []

    def test_price_changed_returns_current_prices_of_all_ordered_menus_in_request_order(self, seeded: AppContainer, t1: int) -> None:
        data = make_order_data([(6, 1), (1, 2)])  # 이전 가격으로 계산한 합계
        seeded.menus.update(1, menu_data(seeded, 1, price=10000))
        with pytest.raises(PriceChanged) as exc:
            seeded.orders.create_order(t1, data)
        assert exc.value.current_prices == [{"menuId": 6, "price": 1000}, {"menuId": 1, "price": 10000}]
        assert seeded.orders.list_session_orders(t1, 0, 10).items == []

    def test_wrong_client_total_is_price_changed_even_without_menu_change(self, seeded: AppContainer, t1: int) -> None:
        with pytest.raises(PriceChanged):
            seeded.orders.create_order(t1, make_order_data([(1, 1)], client_total=1))
        with pytest.raises(PriceChanged):
            seeded.orders.create_order(t1, make_order_data([(1, 1)], client_total=0))

    def test_menu_unavailable_takes_priority_over_price_changed(self, seeded: AppContainer, t1: int) -> None:
        seeded.menus.delete(1)
        with pytest.raises(MenuUnavailable):
            seeded.orders.create_order(t1, make_order_data([(1, 1), (2, 1)], client_total=1))

    def test_price_change_then_retry_with_new_total_succeeds(self, seeded: AppContainer, t1: int) -> None:
        data = make_order_data([(1, 2)])
        seeded.menus.update(1, menu_data(seeded, 1, price=10000))
        with pytest.raises(PriceChanged):
            seeded.orders.create_order(t1, data)
        result = place(seeded, t1, [(1, 2)], client_total=20000)
        assert result.order.total_amount == 20000

    def test_deleted_menu_name_can_be_reused_by_new_menu_with_new_id(self, seeded: AppContainer, t1: int) -> None:
        seeded.menus.delete(1)
        created = seeded.menus.create(MenuData("김치찌개", 9500, "", "메인", None))
        assert created.id not in PRICES
        with pytest.raises(MenuUnavailable):
            place(seeded, t1, [(1, 1)])
        result = seeded.orders.create_order(t1, make_order_data([(created.id, 1)], client_total=9500))
        assert result.order.total_amount == 9500


class TestListSessionOrders:
    def test_newest_first_and_paging(self, seeded: AppContainer, t1: int) -> None:
        ids = [place(seeded, t1).order.id for _ in range(5)]
        p0 = seeded.orders.list_session_orders(t1, 0, 2)
        p1 = seeded.orders.list_session_orders(t1, 1, 2)
        p2 = seeded.orders.list_session_orders(t1, 2, 2)
        assert [o.id for o in p0.items] == ids[::-1][:2] and p0.has_next is True
        assert [o.id for o in p1.items] == ids[::-1][2:4] and p1.has_next is True
        assert [o.id for o in p2.items] == ids[::-1][4:] and p2.has_next is False
        assert (p0.page, p0.size) == (0, 2)

    def test_exact_page_boundary_has_no_next(self, seeded: AppContainer, t1: int) -> None:
        for _ in range(4):
            place(seeded, t1)
        assert seeded.orders.list_session_orders(t1, 1, 2).has_next is False

    def test_page_beyond_end_is_empty(self, seeded: AppContainer, t1: int) -> None:
        place(seeded, t1)
        page = seeded.orders.list_session_orders(t1, 9, 10)
        assert page.items == [] and page.has_next is False

    def test_no_session_gives_empty_page(self, seeded: AppContainer, t1: int) -> None:
        page = seeded.orders.list_session_orders(t1, 0, 10)
        assert (page.items, page.has_next, page.page, page.size) == ([], False, 0, 10)

    def test_isolated_per_table_and_per_session(self, seeded: AppContainer, t1: int) -> None:
        t2 = table_id_of(seeded, 2)
        place(seeded, t1)
        mine = place(seeded, t2).order
        assert [o.id for o in seeded.orders.list_session_orders(t2, 0, 10).items] == [mine.id]
        seeded.tables.end_session(t2)
        new = place(seeded, t2).order
        assert [o.id for o in seeded.orders.list_session_orders(t2, 0, 10).items] == [new.id]


class TestDashboard:
    def test_lists_all_tables_in_number_order_even_without_orders(self, seeded: AppContainer) -> None:
        seeded.tables.register(10, "1111")
        board = seeded.orders.dashboard()
        assert [s.table_number for s in board] == [1, 2, 3, 4, 5, 10]
        assert all(s.session_active is False and s.orders == [] and s.total_amount == 0 for s in board)

    def test_preview_is_latest_three_but_totals_cover_whole_session(self, seeded: AppContainer, t1: int) -> None:
        ids = [place(seeded, t1, [(6, i + 1)]).order.id for i in range(5)]  # 1000원 x 1..5
        summary = seeded.orders.dashboard()[0]
        assert [o.id for o in summary.orders] == ids[::-1][:3]
        assert summary.order_count == 5
        assert summary.total_amount == 1000 * (1 + 2 + 3 + 4 + 5)
        assert summary.session_active is True

    def test_table_filter_returns_single_summary_with_all_orders(self, seeded: AppContainer, t1: int) -> None:
        ids = [place(seeded, t1).order.id for _ in range(5)]
        place(seeded, table_id_of(seeded, 2))
        result = seeded.orders.dashboard(1)
        assert len(result) == 1
        assert [o.id for o in result[0].orders] == ids[::-1]
        assert result[0].order_count == 5

    def test_unknown_table_number(self, seeded: AppContainer) -> None:
        with pytest.raises(NotFound):
            seeded.orders.dashboard(99)

    def test_items_are_attached_to_each_order(self, seeded: AppContainer, t1: int) -> None:
        place(seeded, t1, [(1, 1), (6, 2)])
        place(seeded, table_id_of(seeded, 2), [(8, 4)])
        board = {s.table_number: s for s in seeded.orders.dashboard()}
        assert [i.menu_name for i in board[1].orders[0].items] == ["김치찌개", "공기밥"]
        assert [(i.menu_name, i.quantity) for i in board[2].orders[0].items] == [("콜라", 4)]
        assert board[2].orders[0].table_number == 2

    def test_table_without_orders_in_session_that_was_emptied(self, seeded: AppContainer, t1: int) -> None:
        order = place(seeded, t1).order
        seeded.orders.delete_order(order.id)
        summary = seeded.orders.dashboard(1)[0]
        assert (summary.session_active, summary.order_count, summary.total_amount) == (True, 0, 0)


class TestGetOrder:
    def test_returns_active_order(self, seeded: AppContainer, t1: int) -> None:
        order = place(seeded, t1, [(1, 2)]).order
        assert seeded.orders.get_order(order.id) == order

    def test_unknown_and_archived_orders_are_not_found(self, seeded: AppContainer, t1: int) -> None:
        order = place(seeded, t1).order
        with pytest.raises(NotFound):
            seeded.orders.get_order(99999)
        seeded.tables.end_session(t1)
        with pytest.raises(NotFound):
            seeded.orders.get_order(order.id)


class TestChangeStatus:
    ALL = ["PENDING", "PREPARING", "COMPLETED"]

    def _order_in(self, seeded: AppContainer, t1: int, status: str) -> int:
        oid = place(seeded, t1).order.id
        for step in self.ALL[1 : self.ALL.index(status) + 1]:
            seeded.orders.change_status(oid, step)
        return oid

    @pytest.mark.parametrize(
        "current,requested,allowed",
        [
            (c, r, (c, r) in {("PENDING", "PREPARING"), ("PREPARING", "COMPLETED")})
            for c in ["PENDING", "PREPARING", "COMPLETED"]
            for r in ["PENDING", "PREPARING", "COMPLETED"]
        ],
    )
    def test_transition_table(self, seeded: AppContainer, t1: int, current: str, requested: str, allowed: bool) -> None:
        oid = self._order_in(seeded, t1, current)
        if allowed:
            assert seeded.orders.change_status(oid, requested).status == requested
            assert seeded.orders.get_order(oid).status == requested
        else:
            with pytest.raises(InvalidTransition):
                seeded.orders.change_status(oid, requested)
            assert seeded.orders.get_order(oid).status == current

    def test_unknown_order_is_not_found_before_transition_check(self, seeded: AppContainer) -> None:
        with pytest.raises(NotFound):
            seeded.orders.change_status(12345, "COMPLETED")

    def test_archived_order_is_not_found(self, seeded: AppContainer, t1: int) -> None:
        oid = place(seeded, t1).order.id
        seeded.tables.end_session(t1)
        with pytest.raises(NotFound):
            seeded.orders.change_status(oid, "PREPARING")

    def test_events_only_on_success(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        oid = place(seeded, t1).order.id
        publisher.events.clear()
        with pytest.raises(InvalidTransition):
            seeded.orders.change_status(oid, "COMPLETED")
        assert publisher.events == []
        seeded.orders.change_status(oid, "PREPARING")
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [
            ("order_status_changed", t1, {"orderId": oid, "status": "PREPARING"})
        ]

    def test_concurrent_same_transition_succeeds_once(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        oid = place(seeded, t1).order.id
        publisher.events.clear()
        outcomes: list[str] = []
        barrier = threading.Barrier(4)

        def worker() -> None:
            barrier.wait()
            try:
                seeded.orders.change_status(oid, "PREPARING")
                outcomes.append("ok")
            except InvalidTransition:
                outcomes.append("conflict")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert sorted(outcomes) == ["conflict", "conflict", "conflict", "ok"]
        assert len(publisher.events) == 1


class TestDelete:
    def test_removes_order_and_returns_recalculated_summary(self, seeded: AppContainer, t1: int) -> None:
        a = place(seeded, t1, [(1, 1)]).order
        b = place(seeded, t1, [(2, 1)]).order
        summary = seeded.orders.delete_order(a.id)
        assert (summary.table_id, summary.table_number) == (t1, 1)
        assert summary.order_count == 1 and summary.total_amount == b.total_amount
        assert [o.id for o in summary.orders] == [b.id]
        with pytest.raises(NotFound):
            seeded.orders.get_order(a.id)
        with seeded.db.connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (a.id,)).fetchone()[0] == 0

    def test_completed_order_can_be_deleted(self, seeded: AppContainer, t1: int) -> None:
        oid = place(seeded, t1).order.id
        seeded.orders.change_status(oid, "PREPARING")
        seeded.orders.change_status(oid, "COMPLETED")
        assert seeded.orders.delete_order(oid).order_count == 0

    def test_last_order_deleted_keeps_session_active(self, seeded: AppContainer, t1: int) -> None:
        oid = place(seeded, t1).order.id
        summary = seeded.orders.delete_order(oid)
        assert (summary.session_active, summary.order_count, summary.total_amount, summary.orders) == (True, 0, 0, [])

    def test_summary_preview_is_latest_three(self, seeded: AppContainer, t1: int) -> None:
        ids = [place(seeded, t1).order.id for _ in range(6)]
        summary = seeded.orders.delete_order(ids[0])
        assert [o.id for o in summary.orders] == ids[::-1][:3]
        assert summary.order_count == 5

    def test_unknown_or_archived_order_is_not_found(self, seeded: AppContainer, t1: int) -> None:
        oid = place(seeded, t1).order.id
        with pytest.raises(NotFound):
            seeded.orders.delete_order(99999)
        seeded.tables.end_session(t1)
        with pytest.raises(NotFound):
            seeded.orders.delete_order(oid)

    def test_event_published_after_commit(self, seeded: AppContainer, t1: int, publisher) -> None:  # type: ignore[no-untyped-def]
        oid = place(seeded, t1).order.id
        publisher.events.clear()
        seeded.orders.delete_order(oid)
        assert [(e.type, e.table_id, e.payload) for e in publisher.events] == [("order_deleted", t1, {"orderId": oid})]
        with pytest.raises(NotFound):
            seeded.orders.delete_order(oid)
        assert len(publisher.events) == 1

    def test_order_numbers_are_not_reused_after_delete(self, seeded: AppContainer, t1: int) -> None:
        first = place(seeded, t1).order
        seeded.orders.delete_order(first.id)
        second = place(seeded, t1).order
        assert second.id > first.id and second.order_number != first.order_number
