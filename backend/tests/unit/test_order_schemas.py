from __future__ import annotations

from datetime import date

import pytest

from app.errors import ValidationFailed
from app.schemas import (
    OrderCreateItem,
    OrderCreateRequest,
    OrderOut,
    StatusChangeRequest,
    TableRegisterRequest,
    validate_history_range,
    validate_order_create,
    validate_status,
    validate_table_register,
)
from app.services.order_models import OrderItemRecord, OrderRecord, order_number_for

UUID_A = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"


def make_req(items=None, client_order_id: str = UUID_A, client_total: int = 10000) -> OrderCreateRequest:  # type: ignore[no-untyped-def]
    items = items if items is not None else [(1, 2)]
    return OrderCreateRequest(
        client_order_id=client_order_id,
        items=[OrderCreateItem(menu_id=m, quantity=q) for m, q in items],
        client_total=client_total,
    )


def fields_of(req: OrderCreateRequest) -> dict[str, str]:
    with pytest.raises(ValidationFailed) as exc:
        validate_order_create(req)
    return exc.value.fields


class TestOrderCreateValidation:
    def test_valid_request_normalizes_uuid(self) -> None:
        data = validate_order_create(make_req(client_order_id=UUID_A.upper()))
        assert data.client_order_id == UUID_A
        assert data.items == [(1, 2)]
        assert data.client_total == 10000

    def test_keeps_request_order(self) -> None:
        data = validate_order_create(make_req(items=[(5, 1), (2, 3), (9, 20)]))
        assert data.items == [(5, 1), (2, 3), (9, 20)]

    @pytest.mark.parametrize("qty", [0, -1, 21, 100])
    def test_quantity_out_of_range(self, qty: int) -> None:
        assert fields_of(make_req(items=[(1, qty)]))["items"] == "수량은 1~20 사이로 입력해주세요."

    @pytest.mark.parametrize("qty", [1, 20])
    def test_quantity_boundaries_ok(self, qty: int) -> None:
        assert validate_order_create(make_req(items=[(1, qty)])).items == [(1, qty)]

    def test_empty_items(self) -> None:
        assert fields_of(make_req(items=[]))["items"] == "주문할 메뉴를 선택해주세요."

    def test_thirty_distinct_ok_thirty_one_rejected(self) -> None:
        assert len(validate_order_create(make_req(items=[(i, 1) for i in range(1, 31)])).items) == 30
        assert fields_of(make_req(items=[(i, 1) for i in range(1, 32)]))["items"] == (
            "한 번에 주문할 수 있는 메뉴는 최대 30종류예요."
        )

    def test_duplicate_menu_rejected(self) -> None:
        assert fields_of(make_req(items=[(1, 1), (2, 1), (1, 3)]))["items"] == "같은 메뉴는 한 줄로 합쳐서 주문해주세요."

    @pytest.mark.parametrize("menu_id", [0, -5])
    def test_non_positive_menu_id(self, menu_id: int) -> None:
        assert fields_of(make_req(items=[(menu_id, 1)]))["items"] == "메뉴 정보가 올바르지 않아요."

    @pytest.mark.parametrize("value", ["", "abc", "123", "3f2b8c1e-5d4a-4e6f-9a7b"])
    def test_bad_client_order_id(self, value: str) -> None:
        assert fields_of(make_req(client_order_id=value))["clientOrderId"] == "주문 식별자 형식이 올바르지 않아요."

    def test_negative_total_rejected_zero_allowed_by_format(self) -> None:
        assert fields_of(make_req(client_total=-1))["clientTotal"] == "주문 금액이 올바르지 않아요."
        assert validate_order_create(make_req(client_total=0)).client_total == 0

    def test_all_errors_collected_at_once(self) -> None:
        fields = fields_of(make_req(items=[], client_order_id="x", client_total=-1))
        assert set(fields) == {"clientOrderId", "items", "clientTotal"}


class TestOtherValidation:
    @pytest.mark.parametrize("status", ["PENDING", "PREPARING", "COMPLETED"])
    def test_status_ok(self, status: str) -> None:
        assert validate_status(StatusChangeRequest(status=status)) == status

    @pytest.mark.parametrize("status", ["", "pending", "DONE", "CANCELLED"])
    def test_status_invalid(self, status: str) -> None:
        with pytest.raises(ValidationFailed) as exc:
            validate_status(StatusChangeRequest(status=status))
        assert exc.value.fields == {"status": "주문 상태가 올바르지 않아요."}

    @pytest.mark.parametrize("number", [1, 5, 999])
    def test_table_number_ok(self, number: int) -> None:
        assert validate_table_register(TableRegisterRequest(table_number=number, password="1234")) == (number, "1234")

    @pytest.mark.parametrize("number", [0, -1, 1000])
    def test_table_number_invalid(self, number: int) -> None:
        with pytest.raises(ValidationFailed) as exc:
            validate_table_register(TableRegisterRequest(table_number=number, password="1234"))
        assert exc.value.fields == {"tableNumber": "테이블 번호는 1~999 사이 숫자로 입력해주세요."}

    @pytest.mark.parametrize("password", ["", "123", "12345", "abcd", "12 4", " 1234", "１２３４"])
    def test_table_password_invalid(self, password: str) -> None:
        with pytest.raises(ValidationFailed) as exc:
            validate_table_register(TableRegisterRequest(table_number=1, password=password))
        assert exc.value.fields == {"password": "비밀번호는 숫자 4자리입니다."}

    def test_history_range(self) -> None:
        validate_history_range(None, None)
        validate_history_range(date(2026, 10, 1), None)
        validate_history_range(None, date(2026, 10, 1))
        validate_history_range(date(2026, 10, 1), date(2026, 10, 1))
        with pytest.raises(ValidationFailed) as exc:
            validate_history_range(date(2026, 10, 2), date(2026, 10, 1))
        assert exc.value.fields == {"from": "시작일이 종료일보다 늦을 수 없습니다."}


class TestOrderNumberAndSerialization:
    @pytest.mark.parametrize("order_id,expected", [(1, "0001"), (7, "0007"), (9999, "9999"), (12345, "12345")])
    def test_order_number(self, order_id: int, expected: str) -> None:
        assert order_number_for(order_id) == expected

    def test_order_out_is_camel_case(self) -> None:
        record = OrderRecord(
            id=7,
            order_number="0007",
            table_id=2,
            table_number=3,
            session_id="sess_abc",
            created_at="2026-10-14T00:00:00Z",
            status="PENDING",
            total_amount=18000,
            items=[OrderItemRecord(menu_id=1, menu_name="김치찌개", quantity=2, unit_price=9000)],
        )
        data = OrderOut.model_validate(record, from_attributes=True).model_dump(by_alias=True)
        assert data == {
            "id": 7,
            "orderNumber": "0007",
            "tableId": 2,
            "tableNumber": 3,
            "sessionId": "sess_abc",
            "createdAt": "2026-10-14T00:00:00Z",
            "status": "PENDING",
            "totalAmount": 18000,
            "items": [{"menuId": 1, "menuName": "김치찌개", "quantity": 2, "unitPrice": 9000}],
        }
