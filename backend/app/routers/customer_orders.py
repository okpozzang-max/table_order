"""고객용 주문 라우터: 주문 생성(멱등), 현재 세션 주문 내역."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from ..deps import AppContainer, TablePrincipal, get_container, require_table
from ..schemas import (
    ApiErrorBody,
    OrderCreateRequest,
    OrderOut,
    OrderPageOut,
    validate_order_create,
)

router = APIRouter(prefix="/api/customer")

_ERR = {"model": ApiErrorBody}


@router.post(
    "/orders",
    operation_id="createOrder",
    tags=["customer-orders"],
    summary="주문 생성 (clientOrderId 멱등)",
    status_code=201,
    response_model=OrderOut,
    responses={
        200: {"model": OrderOut, "description": "같은 clientOrderId로 이미 생성된 주문 (멱등 응답)"},
        401: _ERR,
        409: _ERR,
        422: _ERR,
        500: _ERR,
    },
)
def create_order(
    body: OrderCreateRequest,
    response: Response,
    table: TablePrincipal = Depends(require_table),
    container: AppContainer = Depends(get_container),
) -> OrderOut:
    data = validate_order_create(body)
    result = container.orders.create_order(table.table_id, data)
    response.status_code = 201 if result.created else 200
    return OrderOut.model_validate(result.order, from_attributes=True)


@router.get(
    "/orders",
    operation_id="listSessionOrders",
    tags=["customer-orders"],
    summary="현재 테이블 세션의 주문 내역 (최신순)",
    response_model=OrderPageOut,
    responses={401: _ERR, 422: _ERR, 500: _ERR},
)
def list_session_orders(
    page: int = Query(0, ge=0, description="0부터 시작하는 페이지 번호"),
    size: int = Query(10, ge=1, le=50, description="페이지 크기"),
    table: TablePrincipal = Depends(require_table),
    container: AppContainer = Depends(get_container),
) -> OrderPageOut:
    record = container.orders.list_session_orders(table.table_id, page, size)
    return OrderPageOut.model_validate(record, from_attributes=True)
