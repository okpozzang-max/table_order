"""요청/응답 모델(camelCase JSON)과 입력 검증.

- 요청 모델은 타입만 표현한다 (OpenAPI 스키마가 계약과 맞도록). 값 규칙은 validate_* 함수가 필드별 문구로 검사한다.
- 타입 자체가 틀린 입력(문자열 가격 등)은 FastAPI 검증 오류 -> main.py 핸들러가 필드별 문구로 변환한다.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, StrictInt
from pydantic.alias_generators import to_camel

from .errors import ValidationFailed


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---------- 요청 ----------


class TableLoginRequest(ApiModel):
    store_id: str
    table_number: StrictInt
    password: str


class AdminLoginRequest(ApiModel):
    store_id: str
    username: str
    password: str


class MenuInput(ApiModel):
    name: str
    price: StrictInt
    description: str
    category: str
    image_url: str | None


class ReorderRequest(ApiModel):
    category: str
    ordered_ids: list[StrictInt]


class OrderCreateItem(ApiModel):
    menu_id: StrictInt
    quantity: StrictInt


class OrderCreateRequest(ApiModel):
    client_order_id: str
    items: list[OrderCreateItem]
    client_total: StrictInt


class StatusChangeRequest(ApiModel):
    status: str


class TableRegisterRequest(ApiModel):
    table_number: StrictInt
    password: str


# ---------- 응답 ----------


class TokenResponse(ApiModel):
    access_token: str
    expires_at: str


class TableTokenResponse(ApiModel):
    access_token: str
    expires_at: str
    table_id: int
    table_number: int


class MenuOut(ApiModel):
    id: int
    name: str
    price: int
    description: str
    category: str
    image_url: str | None
    display_order: int


class CategoryMenusOut(ApiModel):
    category: str
    menus: list[MenuOut]


class ApiErrorBody(ApiModel):
    code: str
    message: str | None = None
    fields: dict[str, str] | None = None
    retry_after_seconds: int | None = None
    details: dict[str, Any] | None = None


# ---------- 응답 (backend-order) ----------
# 서비스는 dataclass(order_models)를 반환하고 라우터가 model_validate(..., from_attributes=True)로 변환한다.


class OrderItemOut(ApiModel):
    menu_id: int
    menu_name: str
    quantity: int
    unit_price: int


class OrderOut(ApiModel):
    id: int
    order_number: str
    table_id: int
    table_number: int
    session_id: str
    created_at: str
    status: str
    total_amount: int
    items: list[OrderItemOut]


class OrderPageOut(ApiModel):
    items: list[OrderOut]
    page: int
    size: int
    has_next: bool


class TableSummaryOut(ApiModel):
    table_id: int
    table_number: int
    session_active: bool
    total_amount: int
    order_count: int
    orders: list[OrderOut]


class TableInfoOut(ApiModel):
    id: int
    table_number: int
    session_active: bool


class SessionSummaryOut(ApiModel):
    table_id: int
    ended_at: str
    archived_order_count: int
    archived_total_amount: int


class HistoryOrderOut(ApiModel):
    order_id: int
    order_number: str
    table_number: int
    created_at: str
    items: list[OrderItemOut]
    total_amount: int
    completed_at: str


class ServerEventOut(ApiModel):
    """SSE data 본문 (문서화/계약 비교용)."""

    type: str
    table_id: int | None
    payload: dict[str, Any]


# ---------- 검증 ----------

MSG_STORE_ID = "매장 식별자를 입력해주세요."
MSG_TABLE_NUMBER = "테이블 번호는 1~999 사이 숫자로 입력해주세요."
MSG_TABLE_PASSWORD = "비밀번호는 숫자 4자리입니다."
MSG_REQUIRED = "해당 항목을 입력해주세요."
MSG_MENU_NAME = "메뉴명은 1~50자로 입력해주세요."
MSG_PRICE = "가격은 100원~1,000,000원 사이 정수로 입력해주세요."
MSG_DESCRIPTION = "설명은 300자 이내로 입력해주세요."
MSG_CATEGORY = "카테고리는 1~30자로 입력해주세요."
MSG_IMAGE_URL = "이미지 주소는 http 또는 https URL이어야 합니다."
MSG_DUPLICATE_NAME = "같은 카테고리에 같은 이름의 메뉴가 이미 있어요."
MSG_ORDERED_IDS = "해당 카테고리의 모든 메뉴 ID가 필요해요."

_FOUR_DIGITS = re.compile(r"^\d{4}$")
# 테이블 등록은 ASCII 숫자만 허용한다 (전각 숫자 등으로 로그인할 수 없는 비밀번호가 저장되는 것을 방지)
_ASCII_FOUR_DIGITS = re.compile(r"^[0-9]{4}$")


@dataclass(frozen=True)
class MenuData:
    name: str
    price: int
    description: str
    category: str
    image_url: str | None


def _is_http_url(value: str) -> bool:
    if len(value) > 2048 or any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate_table_login(req: TableLoginRequest) -> tuple[str, int, str]:
    errors: dict[str, str] = {}
    store_id = req.store_id.strip()
    if not 1 <= len(store_id) <= 50:
        errors["storeId"] = MSG_STORE_ID
    if not 1 <= req.table_number <= 999:
        errors["tableNumber"] = MSG_TABLE_NUMBER
    if not _FOUR_DIGITS.match(req.password):
        errors["password"] = MSG_TABLE_PASSWORD
    if errors:
        raise ValidationFailed(errors)
    return store_id, req.table_number, req.password


def validate_admin_login(req: AdminLoginRequest) -> tuple[str, str, str]:
    errors: dict[str, str] = {}
    store_id = req.store_id.strip()
    username = req.username.strip()
    if not store_id:
        errors["storeId"] = MSG_REQUIRED
    if not username:
        errors["username"] = MSG_REQUIRED
    if not req.password or len(req.password.encode("utf-8")) > 72:
        errors["password"] = MSG_REQUIRED
    if errors:
        raise ValidationFailed(errors)
    return store_id, username, req.password


def validate_menu_input(req: MenuInput) -> MenuData:
    errors: dict[str, str] = {}
    name = req.name.strip()
    description = req.description.strip()
    category = req.category.strip()
    image_url = (req.image_url or "").strip() or None

    if not 1 <= len(name) <= 50:
        errors["name"] = MSG_MENU_NAME
    if not 100 <= req.price <= 1_000_000:
        errors["price"] = MSG_PRICE
    if len(description) > 300:
        errors["description"] = MSG_DESCRIPTION
    if not 1 <= len(category) <= 30:
        errors["category"] = MSG_CATEGORY
    if image_url is not None and not _is_http_url(image_url):
        errors["imageUrl"] = MSG_IMAGE_URL
    if errors:
        raise ValidationFailed(errors)
    return MenuData(name=name, price=req.price, description=description, category=category, image_url=image_url)


def validate_reorder(req: ReorderRequest) -> tuple[str, list[int]]:
    category = req.category.strip()
    if not 1 <= len(category) <= 30:
        raise ValidationFailed({"category": MSG_CATEGORY})
    return category, list(req.ordered_ids)


# ---------- 검증 (backend-order) ----------

MSG_CLIENT_ORDER_ID = "주문 식별자 형식이 올바르지 않아요."
MSG_ITEMS_EMPTY = "주문할 메뉴를 선택해주세요."
MSG_ITEMS_MAX = "한 번에 주문할 수 있는 메뉴는 최대 30종류예요."
MSG_ITEMS_MENU = "메뉴 정보가 올바르지 않아요."
MSG_ITEMS_QUANTITY = "수량은 1~20 사이로 입력해주세요."
MSG_ITEMS_DUPLICATE = "같은 메뉴는 한 줄로 합쳐서 주문해주세요."
MSG_CLIENT_TOTAL = "주문 금액이 올바르지 않아요."
MSG_STATUS = "주문 상태가 올바르지 않아요."
MSG_DATE_ORDER = "시작일이 종료일보다 늦을 수 없습니다."

MAX_DISTINCT_MENUS = 30
MAX_QUANTITY = 20
ORDER_STATUSES = ("PENDING", "PREPARING", "COMPLETED")


@dataclass(frozen=True)
class OrderCreateData:
    client_order_id: str  # 소문자 정규형 UUID
    items: list[tuple[int, int]]  # (menu_id, quantity) 요청 순서
    client_total: int


def validate_order_create(req: OrderCreateRequest) -> OrderCreateData:
    errors: dict[str, str] = {}

    normalized_id = ""
    try:
        normalized_id = str(uuid.UUID(req.client_order_id.strip()))
    except ValueError:
        errors["clientOrderId"] = MSG_CLIENT_ORDER_ID

    items = [(it.menu_id, it.quantity) for it in req.items]
    distinct = {menu_id for menu_id, _ in items}
    if not items:
        errors["items"] = MSG_ITEMS_EMPTY
    elif len(distinct) > MAX_DISTINCT_MENUS:
        errors["items"] = MSG_ITEMS_MAX
    elif any(menu_id <= 0 for menu_id, _ in items):
        errors["items"] = MSG_ITEMS_MENU
    elif any(not 1 <= qty <= MAX_QUANTITY for _, qty in items):
        errors["items"] = MSG_ITEMS_QUANTITY
    elif len(distinct) != len(items):
        errors["items"] = MSG_ITEMS_DUPLICATE

    if req.client_total < 0:
        errors["clientTotal"] = MSG_CLIENT_TOTAL

    if errors:
        raise ValidationFailed(errors)
    return OrderCreateData(client_order_id=normalized_id, items=items, client_total=req.client_total)


def validate_status(req: StatusChangeRequest) -> str:
    if req.status not in ORDER_STATUSES:
        raise ValidationFailed({"status": MSG_STATUS})
    return req.status


def validate_table_register(req: TableRegisterRequest) -> tuple[int, str]:
    errors: dict[str, str] = {}
    if not 1 <= req.table_number <= 999:
        errors["tableNumber"] = MSG_TABLE_NUMBER
    if not _ASCII_FOUR_DIGITS.match(req.password):
        errors["password"] = MSG_TABLE_PASSWORD
    if errors:
        raise ValidationFailed(errors)
    return req.table_number, req.password


def validate_history_range(from_date: date | None, to_date: date | None) -> None:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ValidationFailed({"from": MSG_DATE_ORDER})
