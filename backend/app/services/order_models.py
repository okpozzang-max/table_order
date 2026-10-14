"""backend-order 서비스가 반환하는 값 객체. HTTP/JSON 표현(schemas.py의 *Out)과 분리한다."""

from __future__ import annotations

from dataclasses import dataclass, field


def order_number_for(order_id: int) -> str:
    """주문 번호: 주문 ID를 4자리로 채운 값 (저장하지 않고 항상 ID에서 계산한다)."""
    return str(order_id).zfill(4)


@dataclass(frozen=True)
class OrderItemRecord:
    menu_id: int
    menu_name: str
    quantity: int
    unit_price: int


@dataclass(frozen=True)
class OrderRecord:
    id: int
    order_number: str
    table_id: int
    table_number: int
    session_id: str
    created_at: str
    status: str
    total_amount: int
    items: list[OrderItemRecord] = field(default_factory=list)


@dataclass(frozen=True)
class CreateOrderResult:
    order: OrderRecord
    created: bool  # False면 멱등 재응답


@dataclass(frozen=True)
class OrderPageRecord:
    items: list[OrderRecord]
    page: int
    size: int
    has_next: bool


@dataclass(frozen=True)
class TableSummaryRecord:
    table_id: int
    table_number: int
    session_active: bool
    total_amount: int
    order_count: int
    orders: list[OrderRecord] = field(default_factory=list)


@dataclass(frozen=True)
class TableInfoRecord:
    id: int
    table_number: int
    session_active: bool


@dataclass(frozen=True)
class SessionSummaryRecord:
    table_id: int
    ended_at: str
    archived_order_count: int
    archived_total_amount: int


@dataclass(frozen=True)
class HistoryOrderRecord:
    order_id: int
    order_number: str
    table_number: int
    created_at: str
    items: list[OrderItemRecord]
    total_amount: int
    completed_at: str
