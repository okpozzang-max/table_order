"""관리자용 테이블 라우터: 목록, 등록, 이용 완료, 과거 주문 내역."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from ..deps import AdminPrincipal, AppContainer, get_container, require_admin
from ..schemas import (
    ApiErrorBody,
    HistoryOrderOut,
    SessionSummaryOut,
    TableInfoOut,
    TableRegisterRequest,
    validate_history_range,
    validate_table_register,
)

router = APIRouter(prefix="/api/admin")

_ERR = {"model": ApiErrorBody}


@router.get(
    "/tables",
    operation_id="listTables",
    tags=["admin-tables"],
    summary="등록된 테이블 목록 (번호 오름차순)",
    response_model=list[TableInfoOut],
    responses={401: _ERR, 500: _ERR},
)
def list_tables(
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> list[TableInfoOut]:
    return [TableInfoOut.model_validate(t, from_attributes=True) for t in container.tables.list_tables()]


@router.post(
    "/tables",
    operation_id="registerTable",
    tags=["admin-tables"],
    summary="테이블 등록 (번호 + 숫자 4자리 비밀번호)",
    status_code=201,
    response_model=TableInfoOut,
    responses={401: _ERR, 409: _ERR, 422: _ERR, 500: _ERR},
)
def register_table(
    body: TableRegisterRequest,
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> TableInfoOut:
    table_number, password = validate_table_register(body)
    return TableInfoOut.model_validate(container.tables.register(table_number, password), from_attributes=True)


@router.post(
    "/tables/{tableId}/end-session",
    operation_id="endSession",
    tags=["admin-tables"],
    summary="테이블 이용 완료 (세션 종료, 주문을 과거 이력으로 이동)",
    response_model=SessionSummaryOut,
    responses={401: _ERR, 404: _ERR, 409: _ERR, 422: _ERR, 500: _ERR},
)
def end_session(
    tableId: int,  # noqa: N803  (경로 변수 이름은 계약과 같아야 한다)
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> SessionSummaryOut:
    return SessionSummaryOut.model_validate(container.tables.end_session(tableId), from_attributes=True)


@router.get(
    "/tables/{tableId}/history",
    operation_id="getTableHistory",
    tags=["admin-tables"],
    summary="테이블 과거 주문 내역 (시간 역순, 날짜 필터)",
    response_model=list[HistoryOrderOut],
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def get_table_history(
    tableId: int,  # noqa: N803
    from_: date | None = Query(None, alias="from", description="시작일 (포함)"),
    to: date | None = Query(None, description="종료일 (포함)"),
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> list[HistoryOrderOut]:
    validate_history_range(from_, to)
    records = container.tables.get_history(tableId, from_, to)
    return [HistoryOrderOut.model_validate(r, from_attributes=True) for r in records]
