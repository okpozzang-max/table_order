"""고객용 라우터: 테이블 로그인, 메뉴 조회."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import AppContainer, TablePrincipal, get_container, require_table
from ..schemas import (
    ApiErrorBody,
    CategoryMenusOut,
    MenuOut,
    TableLoginRequest,
    TableTokenResponse,
    validate_table_login,
)
from ..timeutil import utc_iso

router = APIRouter(prefix="/api/customer")

_ERR = {"model": ApiErrorBody}


def to_category_menus_out(groups) -> list[CategoryMenusOut]:  # type: ignore[no-untyped-def]
    return [
        CategoryMenusOut(
            category=g.category,
            menus=[
                MenuOut(
                    id=m.id,
                    name=m.name,
                    price=m.price,
                    description=m.description,
                    category=m.category,
                    image_url=m.image_url,
                    display_order=m.display_order,
                )
                for m in g.menus
            ],
        )
        for g in groups
    ]


@router.post(
    "/auth/login",
    operation_id="customerLogin",
    tags=["customer-auth"],
    summary="테이블 로그인 (자동 로그인 포함)",
    response_model=TableTokenResponse,
    responses={401: _ERR, 422: _ERR, 429: _ERR, 500: _ERR},
)
def customer_login(body: TableLoginRequest, container: AppContainer = Depends(get_container)) -> TableTokenResponse:
    store_id, table_number, password = validate_table_login(body)
    result = container.auth.login_table(store_id, table_number, password)
    return TableTokenResponse(
        access_token=result.access_token,
        expires_at=utc_iso(result.expires_at),
        table_id=result.table_id,
        table_number=result.table_number,
    )


@router.get(
    "/menus",
    operation_id="getCustomerMenus",
    tags=["customer-menu"],
    summary="카테고리별 메뉴 조회 (노출 순서 반영)",
    response_model=list[CategoryMenusOut],
    responses={401: _ERR, 500: _ERR},
)
def get_customer_menus(
    _table: TablePrincipal = Depends(require_table),
    container: AppContainer = Depends(get_container),
) -> list[CategoryMenusOut]:
    return to_category_menus_out(container.menus.list_grouped())
