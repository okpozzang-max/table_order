"""관리자용 라우터: 로그인, 메뉴 관리.

주의: `/menus/reorder`는 `/menus/{menu_id}`보다 먼저 등록해야 한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..deps import AdminPrincipal, AppContainer, get_container, require_admin
from ..schemas import (
    AdminLoginRequest,
    ApiErrorBody,
    CategoryMenusOut,
    MenuInput,
    MenuOut,
    ReorderRequest,
    TokenResponse,
    validate_admin_login,
    validate_menu_input,
    validate_reorder,
)
from ..timeutil import utc_iso
from .customer import to_category_menus_out

router = APIRouter(prefix="/api/admin")

_ERR = {"model": ApiErrorBody}


def _menu_out(m) -> MenuOut:  # type: ignore[no-untyped-def]
    return MenuOut(
        id=m.id,
        name=m.name,
        price=m.price,
        description=m.description,
        category=m.category,
        image_url=m.image_url,
        display_order=m.display_order,
    )


@router.post(
    "/auth/login",
    operation_id="adminLogin",
    tags=["admin-auth"],
    summary="관리자 로그인 (연속 5회 실패 시 15분 잠금)",
    response_model=TokenResponse,
    responses={401: _ERR, 422: _ERR, 429: _ERR, 500: _ERR},
)
def admin_login(body: AdminLoginRequest, container: AppContainer = Depends(get_container)) -> TokenResponse:
    store_id, username, password = validate_admin_login(body)
    result = container.auth.login_admin(store_id, username, password)
    return TokenResponse(access_token=result.access_token, expires_at=utc_iso(result.expires_at))


@router.get(
    "/menus",
    operation_id="listAdminMenus",
    tags=["admin-menus"],
    summary="카테고리별 메뉴 조회",
    response_model=list[CategoryMenusOut],
    responses={401: _ERR, 500: _ERR},
)
def list_admin_menus(
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> list[CategoryMenusOut]:
    return to_category_menus_out(container.menus.list_grouped())


@router.post(
    "/menus",
    operation_id="createMenu",
    tags=["admin-menus"],
    summary="메뉴 등록",
    status_code=201,
    response_model=MenuOut,
    responses={401: _ERR, 422: _ERR, 500: _ERR},
)
def create_menu(
    body: MenuInput,
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> MenuOut:
    return _menu_out(container.menus.create(validate_menu_input(body)))


@router.put(
    "/menus/reorder",
    operation_id="reorderMenus",
    tags=["admin-menus"],
    summary="카테고리 내 메뉴 노출 순서 변경",
    status_code=204,
    response_class=Response,
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def reorder_menus(
    body: ReorderRequest,
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> Response:
    category, ordered_ids = validate_reorder(body)
    container.menus.reorder(category, ordered_ids)
    return Response(status_code=204)


@router.put(
    "/menus/{menuId}",  # 경로 변수 이름은 계약(contracts/openapi.yaml)과 같아야 한다
    operation_id="updateMenu",
    tags=["admin-menus"],
    summary="메뉴 수정",
    response_model=MenuOut,
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def update_menu(
    menuId: int,  # noqa: N803
    body: MenuInput,
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> MenuOut:
    return _menu_out(container.menus.update(menuId, validate_menu_input(body)))


@router.delete(
    "/menus/{menuId}",
    operation_id="deleteMenu",
    tags=["admin-menus"],
    summary="메뉴 삭제 (소프트 삭제)",
    status_code=204,
    response_class=Response,
    responses={401: _ERR, 404: _ERR, 422: _ERR, 500: _ERR},
)
def delete_menu(
    menuId: int,  # noqa: N803
    _admin: AdminPrincipal = Depends(require_admin),
    container: AppContainer = Depends(get_container),
) -> Response:
    container.menus.delete(menuId)
    return Response(status_code=204)
