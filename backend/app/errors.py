"""도메인 예외와 오류 응답 본문(ApiErrorBody) 생성.

서비스는 HTTP를 모른다. 도메인 예외만 던지고, 앱 계층(main.py)이 상태 코드와 본문으로 변환한다.
backend-order 등 다른 Unit은 AppError를 상속해 같은 체계에 새 오류를 추가한다.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """모든 도메인 예외의 기반 클래스."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "문제가 발생했어요. 잠시 후 다시 시도해주세요."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message

    @property
    def fields(self) -> dict[str, str] | None:
        return None

    @property
    def retry_after_seconds(self) -> int | None:
        return None

    @property
    def details(self) -> dict[str, Any] | None:
        return None

    @property
    def headers(self) -> dict[str, str]:
        return {}

    def to_body(self) -> dict[str, Any]:
        return error_body(
            self.code,
            self.message,
            fields=self.fields,
            retry_after_seconds=self.retry_after_seconds,
            details=self.details,
        )


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    default_message = "입력한 내용을 확인해주세요."

    def __init__(self, fields: dict[str, str], message: str | None = None) -> None:
        super().__init__(message)
        self._fields = dict(fields)

    @property
    def fields(self) -> dict[str, str]:
        return self._fields


class InvalidCredentials(AppError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    default_message = "로그인 정보가 맞지 않아요."


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "로그인이 필요하거나 만료되었어요."

    @property
    def headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": "Bearer"}


class AccountLocked(AppError):
    status_code = 429
    code = "ACCOUNT_LOCKED"
    default_message = "로그인 시도가 너무 많아요. 잠시 후 다시 시도해주세요."

    def __init__(self, retry_after_seconds: int, message: str | None = None) -> None:
        super().__init__(message)
        self._retry_after = max(1, int(retry_after_seconds))

    @property
    def retry_after_seconds(self) -> int:
        return self._retry_after

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self._retry_after)}


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "대상을 찾을 수 없어요."


# ---------- backend-order ----------


class MenuUnavailable(AppError):
    """주문한 메뉴 중 삭제되었거나 없는 메뉴가 있다."""

    status_code = 409
    code = "MENU_UNAVAILABLE"
    default_message = "판매하지 않는 메뉴가 있어요."

    def __init__(self, menu_ids: list[int], message: str | None = None) -> None:
        super().__init__(message)
        self.menu_ids = sorted(set(menu_ids))

    @property
    def details(self) -> dict[str, Any]:
        return {"menuIds": self.menu_ids}


class PriceChanged(AppError):
    """클라이언트 합계가 서버가 계산한 현재 가격 합계와 다르다."""

    status_code = 409
    code = "PRICE_CHANGED"
    default_message = "메뉴 가격이 변경되었어요."

    def __init__(self, current_prices: list[dict[str, int]], message: str | None = None) -> None:
        super().__init__(message)
        self.current_prices = list(current_prices)

    @property
    def details(self) -> dict[str, Any]:
        return {"currentPrices": self.current_prices}


class InvalidTransition(AppError):
    status_code = 409
    code = "INVALID_TRANSITION"
    default_message = "주문 상태를 해당 순서로 바꿀 수 없어요."

    def __init__(self, current: str | None = None, requested: str | None = None, message: str | None = None) -> None:
        super().__init__(message)
        self.current = current
        self.requested = requested


class NoActiveSession(AppError):
    status_code = 409
    code = "NO_ACTIVE_SESSION"
    default_message = "이용 중인 세션이 없어요."


class DuplicateTable(AppError):
    status_code = 409
    code = "DUPLICATE_TABLE"
    default_message = "이미 등록된 테이블 번호예요."

    def __init__(self, table_number: int | None = None, message: str | None = None) -> None:
        super().__init__(message)
        self.table_number = table_number


def error_body(
    code: str,
    message: str | None = None,
    *,
    fields: dict[str, str] | None = None,
    retry_after_seconds: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """계약의 ApiErrorBody 형식. 값이 없는 키는 생략한다."""
    body: dict[str, Any] = {"code": code}
    if message:
        body["message"] = message
    if fields:
        body["fields"] = fields
    if retry_after_seconds is not None:
        body["retryAfterSeconds"] = retry_after_seconds
    if details:
        body["details"] = details
    return body


# FastAPI/Pydantic 요청 검증 오류를 필드별 한국어 문구로 바꾸는 표.
# 필드명이 모델마다 뜻이 다른 경우(storeId, password)는 포함하지 않고 일반 문구를 쓴다.
FIELD_MESSAGES: dict[str, str] = {
    "tableNumber": "테이블 번호는 1~999 사이 숫자로 입력해주세요.",
    "username": "해당 항목을 입력해주세요.",
    "name": "메뉴명은 1~50자로 입력해주세요.",
    "price": "가격은 100원~1,000,000원 사이 정수로 입력해주세요.",
    "description": "설명은 300자 이내로 입력해주세요.",
    "category": "카테고리는 1~30자로 입력해주세요.",
    "imageUrl": "이미지 주소는 http 또는 https URL이어야 합니다.",
    "orderedIds": "해당 카테고리의 모든 메뉴 ID가 필요해요.",
    # backend-order
    "items": "수량은 1~20 사이로 입력해주세요.",
    "clientOrderId": "주문 식별자 형식이 올바르지 않아요.",
    "clientTotal": "주문 금액이 올바르지 않아요.",
    "status": "주문 상태가 올바르지 않아요.",
    "from": "날짜 형식이 올바르지 않아요.",
    "to": "날짜 형식이 올바르지 않아요.",
    "page": "해당 값의 범위가 올바르지 않아요.",
    "size": "해당 값의 범위가 올바르지 않아요.",
    "table": "테이블 번호는 1 이상 숫자로 입력해주세요.",
    "orderId": "형식이 올바르지 않아요.",
    "tableId": "형식이 올바르지 않아요.",
}
GENERIC_FIELD_MESSAGE = "입력 형식이 올바르지 않아요."
BODY_FORMAT_MESSAGE = "요청 본문 형식이 올바르지 않아요."


def fields_from_request_errors(errors: list[dict[str, Any]]) -> dict[str, str]:
    """Pydantic 오류 목록 -> {필드: 문구}. 위치가 body 전체이면 'body' 키를 사용한다."""
    result: dict[str, str] = {}
    for err in errors:
        loc = [p for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        if not loc or isinstance(loc[0], int):  # 본문 전체 오류 (예: JSON 파싱 실패는 loc=('body', 0))
            result.setdefault("body", BODY_FORMAT_MESSAGE)
            continue
        field = str(loc[0])
        result.setdefault(field, FIELD_MESSAGES.get(field, GENERIC_FIELD_MESSAGE))
    return result
