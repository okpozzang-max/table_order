"""공통 테스트 도구: 주문 생성 데이터 만들기."""

from __future__ import annotations

import uuid

from app.deps import AppContainer
from app.schemas import OrderCreateData
from app.services.order_models import CreateOrderResult

# scripts/seed.py 의 메뉴 가격 (ID는 삽입 순서 1..12)
PRICES = {1: 9000, 2: 8500, 3: 11000, 4: 9500, 5: 6000, 6: 1000, 7: 8000, 8: 2000, 9: 2000, 10: 4500, 11: 3000, 12: 3500}


def make_order_data(
    items: list[tuple[int, int]], *, client_order_id: str | None = None, client_total: int | None = None
) -> OrderCreateData:
    total = sum(PRICES[m] * q for m, q in items) if client_total is None else client_total
    return OrderCreateData(client_order_id=client_order_id or str(uuid.uuid4()), items=items, client_total=total)


def place(
    container: AppContainer,
    table_id: int,
    items: list[tuple[int, int]] | None = None,
    **kwargs: object,
) -> CreateOrderResult:
    return container.orders.create_order(table_id, make_order_data(items or [(1, 1)], **kwargs))  # type: ignore[arg-type]


def table_id_of(container: AppContainer, table_number: int) -> int:
    return next(t.id for t in container.tables.list_tables() if t.table_number == table_number)
