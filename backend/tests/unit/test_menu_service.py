from __future__ import annotations

import pytest

from app.deps import AppContainer
from app.errors import NotFound, ValidationFailed
from app.events_port import ServerEvent
from app.schemas import MenuData
from app.services.menu_service import MenuService
from tests.conftest import FakeClock, RecordingPublisher


def data(name: str = "라면", category: str = "분식", price: int = 4000, **kw: object) -> MenuData:
    return MenuData(
        name=name,
        price=price,
        description=str(kw.get("description", "")),
        category=category,
        image_url=kw.get("image_url"),  # type: ignore[arg-type]
    )


@pytest.fixture
def menus(container: AppContainer) -> MenuService:
    return container.menus  # 빈 DB (시드 없음)


def names(service: MenuService, category: str) -> list[str]:
    for g in service.list_grouped():
        if g.category == category:
            return [m.name for m in g.menus]
    return []


class TestOrdering:
    def test_new_menu_goes_last_in_category_and_categories_keep_creation_order(self, menus: MenuService) -> None:
        menus.create(data("a", "메인"))
        menus.create(data("b", "사이드"))
        menus.create(data("c", "메인"))
        menus.create(data("d", "음료"))
        groups = menus.list_grouped()
        assert [g.category for g in groups] == ["메인", "사이드", "음료"]
        assert [m.name for m in groups[0].menus] == ["a", "c"]
        assert [m.display_order for m in groups[0].menus] == [1, 2]

    def test_category_order_is_stable_when_other_menus_are_deleted(self, menus: MenuService) -> None:
        a = menus.create(data("a", "메인"))
        menus.create(data("b", "사이드"))
        menus.create(data("c", "음료"))
        menus.delete(a.id)  # 첫 카테고리가 사라져도
        assert [g.category for g in menus.list_grouped()] == ["사이드", "음료"]
        menus.create(data("a2", "메인"))  # 다시 만들면 맨 뒤
        assert [g.category for g in menus.list_grouped()] == ["사이드", "음료", "메인"]

    def test_delete_renumbers_remaining_menus(self, menus: MenuService) -> None:
        ids = [menus.create(data(n, "메인")).id for n in "abc"]
        menus.delete(ids[0])
        remaining = menus.list_grouped()[0].menus
        assert [(m.name, m.display_order) for m in remaining] == [("b", 1), ("c", 2)]

    def test_move_to_other_category_appends_and_renumbers_old(self, menus: MenuService) -> None:
        a = menus.create(data("a", "메인"))
        menus.create(data("b", "메인"))
        menus.create(data("c", "사이드"))
        moved = menus.update(a.id, data("a", "사이드"))
        assert moved.display_order == 2
        assert names(menus, "사이드") == ["c", "a"]
        assert [(m.name, m.display_order) for m in menus.list_grouped()[0].menus] == [("b", 1)]

    def test_move_to_new_category_creates_it_last(self, menus: MenuService) -> None:
        a = menus.create(data("a", "메인"))
        menus.create(data("b", "사이드"))
        menus.update(a.id, data("a", "신규"))
        assert [g.category for g in menus.list_grouped()] == ["사이드", "신규"]

    def test_update_in_same_category_keeps_position(self, menus: MenuService) -> None:
        a = menus.create(data("a", "메인"))
        menus.create(data("b", "메인"))
        updated = menus.update(a.id, data("a2", "메인", price=5000, description="d", image_url="https://x.test/a.png"))
        assert (updated.name, updated.price, updated.description, updated.display_order) == ("a2", 5000, "d", 1)
        assert updated.image_url == "https://x.test/a.png"
        assert names(menus, "메인") == ["a2", "b"]

    def test_reorder_sets_display_order_one_to_n(self, menus: MenuService) -> None:
        ids = [menus.create(data(n, "메인")).id for n in "abc"]
        menus.reorder("메인", [ids[2], ids[0], ids[1]])
        assert [(m.name, m.display_order) for m in menus.list_grouped()[0].menus] == [("c", 1), ("a", 2), ("b", 3)]

    @pytest.mark.parametrize("bad", ["missing", "extra", "duplicate", "foreign"])
    def test_reorder_requires_exact_set_of_ids(self, menus: MenuService, bad: str) -> None:
        ids = [menus.create(data(n, "메인")).id for n in "abc"]
        other = menus.create(data("x", "사이드")).id
        attempt = {
            "missing": ids[:2],
            "extra": ids + [999],
            "duplicate": [ids[0], ids[0], ids[1]],
            "foreign": [ids[0], ids[1], other],
        }[bad]
        with pytest.raises(ValidationFailed) as exc:
            menus.reorder("메인", attempt)
        assert "orderedIds" in exc.value.fields
        assert names(menus, "메인") == ["a", "b", "c"]  # 변경 없음

    def test_reorder_unknown_category_is_not_found(self, menus: MenuService) -> None:
        with pytest.raises(NotFound):
            menus.reorder("없음", [])

    def test_reorder_ignores_deleted_menus(self, menus: MenuService) -> None:
        ids = [menus.create(data(n, "메인")).id for n in "abc"]
        menus.delete(ids[1])
        menus.reorder("메인", [ids[2], ids[0]])
        assert names(menus, "메인") == ["c", "a"]
        with pytest.raises(ValidationFailed):
            menus.reorder("메인", ids)  # 삭제된 ID 포함


class TestSoftDeleteAndNames:
    def test_deleted_menu_is_hidden_and_name_reusable(self, menus: MenuService) -> None:
        first = menus.create(data("라면"))
        menus.delete(first.id)
        assert menus.list_grouped() == []
        again = menus.create(data("라면"))
        assert again.id != first.id  # ID 재사용 안 함

    def test_deleted_row_is_kept_with_deleted_at(self, menus: MenuService, container: AppContainer) -> None:
        m = menus.create(data("라면"))
        menus.delete(m.id)
        with container.db.connection() as conn:
            row = conn.execute("SELECT deleted_at FROM menus WHERE id=?", (m.id,)).fetchone()
        assert row["deleted_at"]

    def test_delete_twice_and_update_deleted_are_not_found(self, menus: MenuService) -> None:
        m = menus.create(data("라면"))
        menus.delete(m.id)
        with pytest.raises(NotFound):
            menus.delete(m.id)
        with pytest.raises(NotFound):
            menus.update(m.id, data("라면2"))
        with pytest.raises(NotFound):
            menus.delete(12345)

    def test_duplicate_name_in_same_category_is_rejected(self, menus: MenuService) -> None:
        menus.create(data("라면", "분식"))
        with pytest.raises(ValidationFailed) as exc:
            menus.create(data("라면", "분식"))
        assert "name" in exc.value.fields
        menus.create(data("라면", "다른"))  # 다른 카테고리는 허용

    def test_update_duplicate_excludes_self(self, menus: MenuService) -> None:
        a = menus.create(data("a"))
        b = menus.create(data("b"))
        menus.update(a.id, data("a", price=5000))  # 자기 자신과는 충돌하지 않음
        with pytest.raises(ValidationFailed):
            menus.update(b.id, data("a"))
        with pytest.raises(ValidationFailed):  # 카테고리 이동 시 대상 카테고리의 이름과 충돌
            menus.create(data("b", "다른"))
            menus.update(a.id, data("b", "다른"))

    def test_get_active_menus_by_ids_excludes_deleted(self, menus: MenuService) -> None:
        a = menus.create(data("a"))
        b = menus.create(data("b"))
        menus.delete(b.id)
        found = menus.get_active_menus_by_ids([a.id, b.id, 999])
        assert set(found) == {a.id}
        assert found[a.id].price == 4000
        assert menus.get_active_menus_by_ids([]) == {}


class TestEvents:
    def test_menu_changed_is_published_after_each_successful_change(
        self, menus: MenuService, publisher: RecordingPublisher
    ) -> None:
        m = menus.create(data("a", "메인"))
        menus.create(data("b", "메인"))
        menus.update(m.id, data("a2", "메인"))
        menus.reorder("메인", [2, 1])
        menus.delete(m.id)
        assert [e.type for e in publisher.events] == ["menu_changed"] * 5

    def test_no_event_when_operation_fails(self, menus: MenuService, publisher: RecordingPublisher) -> None:
        menus.create(data("a"))
        publisher.events.clear()
        with pytest.raises(ValidationFailed):
            menus.create(data("a"))
        with pytest.raises(NotFound):
            menus.delete(999)
        assert publisher.events == []

    def test_event_is_published_after_commit(self, container: AppContainer, clock: FakeClock) -> None:
        seen: list[int] = []

        class CheckingPublisher:
            def publish(self, event: ServerEvent) -> None:
                with container.db.connection() as conn:  # 발행 시점에 이미 커밋되어 보여야 한다
                    seen.append(conn.execute("SELECT COUNT(*) AS n FROM menus").fetchone()["n"])

        service = MenuService(db=container.db, clock=clock, publisher=CheckingPublisher())
        service.create(data("a"))
        assert seen == [1]

    def test_publisher_failure_does_not_fail_the_request(self, container: AppContainer, clock: FakeClock) -> None:
        class Broken:
            def publish(self, event: ServerEvent) -> None:
                raise RuntimeError("down")

        service = MenuService(db=container.db, clock=clock, publisher=Broken())
        assert service.create(data("a")).name == "a"

    def test_default_publisher_is_noop(self, container: AppContainer, clock: FakeClock) -> None:
        service = MenuService(db=container.db, clock=clock)
        service.create(data("a"))  # 예외 없이 동작
