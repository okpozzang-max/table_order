"""관리자용 주문 라우터: 대시보드, 주문 상세/상태 변경/삭제, 실시간 이벤트 스트림(SSE)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..deps import AdminPrincipal, AppContainer, get_container, require_admin
from ..events import stream_events
from ..schemas import (
    ApiErrorBody,
    OrderOut,
    ServerEventOut,
    StatusChangeRequest,
    TableSummaryOut,
    validate_status,
)

router = APIRouter(prefix="/api/admin")

_ERR = {"model": ApiErrorBody}


@router.get(
    "/dashboard",
    operation_id="getDashboard",
    tags=["admin-orders"],
    summary="테이블별 주문 요약 (테이블 번호 오름차순)",
    response_model=list[TableSummaryOut],
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def get_dashboard(
    table: int | None = Query(
        None, ge=1, description="지정하면 해당 테이블의 현재 세션 전체 주문을 반환한다."
    ),
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> list[TableSummaryOut]:
    records = container.orders.dashboard(table)
    return [TableSummaryOut.model_validate(r, from_attributes=True) for r in records]


@router.get(
    "/orders/{orderId}",
    operation_id="getOrder",
    tags=["admin-orders"],
    summary="주문 상세",
    response_model=OrderOut,
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def get_order(
    orderId: int,  # noqa: N803  (경로 변수 이름은 계약과 같아야 한다)
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> OrderOut:
    return OrderOut.model_validate(container.orders.get_order(orderId), from_attributes=True)


@router.delete(
    "/orders/{orderId}",
    operation_id="deleteOrder",
    tags=["admin-orders"],
    summary="주문 삭제 (직권 수정). 삭제 후 갱신된 테이블 요약 반환",
    response_model=TableSummaryOut,
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def delete_order(
    orderId: int,  # noqa: N803
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> TableSummaryOut:
    return TableSummaryOut.model_validate(container.orders.delete_order(orderId), from_attributes=True)


@router.patch(
    "/orders/{orderId}/status",
    operation_id="changeOrderStatus",
    tags=["admin-orders"],
    summary="주문 상태 변경 (순차 전이만)",
    response_model=OrderOut,
    responses={401: _ERR, 404: _ERR, 409: _ERR, 422: _ERR, 500: _ERR},
)
def change_order_status(
    orderId: int,  # noqa: N803
    body: StatusChangeRequest,
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> OrderOut:
    new_status = validate_status(body)
    return OrderOut.model_validate(container.orders.change_status(orderId, new_status), from_attributes=True)


@router.get(
    "/events",
    operation_id="streamAdminEvents",
    tags=["admin-orders"],
    summary="실시간 이벤트 스트림 (SSE)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "text/event-stream. 각 이벤트의 data는 ServerEvent JSON.",
            "content": {"text/event-stream": {"schema": ServerEventOut.model_json_schema(by_alias=True)}},
        },
        401: _ERR,
        500: _ERR,
    },
)
async def stream_admin_events(
    admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    # 인증(401)은 스트림을 열기 전에 끝난다. 구독은 스트림의 첫 프레임(`: connected`) 직전에 이루어진다.
    frames = stream_events(
        container.broker,
        keepalive_seconds=container.settings.sse_keepalive_seconds,
        expires_at=admin.expires_at,
        now=container.clock,
    )
    return StreamingResponse(
        frames,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
