"""backend-core(8개)와 backend-order(11개) operation이 contracts/openapi.yaml 과 일치하는지 검증한다.

비교 항목: 경로/메서드, 성공/오류 상태 코드 집합, 보안 스킴, 요청·응답 스키마의 모양(속성 이름과 중첩, 타입),
경로/쿼리 파라미터(이름, 위치, 필수 여부, 타입, 범위), 오류 응답 본문 스키마(ApiErrorBody),
실제 응답이 계약의 필수 필드를 포함하는지.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.events import format_sse
from app.events_port import ServerEvent
from tests.conftest import STORE_ID, TABLE_PASSWORD, bearer, login_admin, login_table

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"

BACKEND_CORE_OPERATIONS = [
    "customerLogin",
    "getCustomerMenus",
    "adminLogin",
    "listAdminMenus",
    "createMenu",
    "reorderMenus",
    "updateMenu",
    "deleteMenu",
]

BACKEND_ORDER_OPERATIONS = [
    "createOrder",
    "listSessionOrders",
    "getDashboard",
    "getOrder",
    "deleteOrder",
    "changeOrderStatus",
    "streamAdminEvents",
    "listTables",
    "registerTable",
    "endSession",
    "getTableHistory",
]

ALL_OPERATIONS = BACKEND_CORE_OPERATIONS + BACKEND_ORDER_OPERATIONS

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def app_spec(app) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return app.openapi()


def operations(spec: dict[str, Any]) -> dict[str, tuple[str, str, dict[str, Any]]]:
    found: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS and "operationId" in op:
                found[op["operationId"]] = (path, method, op)
    return found


def resolve(spec: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        target: Any = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        node = target
    return node


def shape(spec: dict[str, Any], node: dict[str, Any]) -> Any:
    """스키마의 '모양'(속성 이름·중첩·기본 타입)만 추출한다. nullable/format/제약은 무시."""
    node = resolve(spec, node)
    if "anyOf" in node:  # Pydantic의 nullable 표현
        non_null = [n for n in node["anyOf"] if resolve(spec, n).get("type") != "null"]
        return shape(spec, non_null[0]) if len(non_null) == 1 else "union"
    if node.get("type") == "array":
        return ["array", shape(spec, node["items"])]
    if "properties" in node:
        return {name: shape(spec, sub) for name, sub in node["properties"].items()}
    return node.get("type", "any")


def required(spec: dict[str, Any], node: dict[str, Any]) -> set[str]:
    node = resolve(spec, node)
    if node.get("type") == "array":
        return required(spec, node["items"])
    return set(node.get("required", []))


def json_schema(op: dict[str, Any], code: str | None = None) -> dict[str, Any] | None:
    if code is None:
        body = op.get("requestBody")
        content = body.get("content", {}) if body else {}
    else:
        content = op.get("responses", {}).get(code, {}).get("content", {})
    media = content.get("application/json")
    return media["schema"] if media else None


def codes(op: dict[str, Any]) -> tuple[set[str], set[str]]:
    all_codes = {str(c) for c in op["responses"]}
    success = {c for c in all_codes if c.startswith("2")}
    return success, all_codes - success


def parameters(spec: dict[str, Any], path_item: dict[str, Any], op: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """경로 수준 + operation 수준 파라미터를 (이름, 위치) -> {required, type, format, minimum, maximum, default}로 정규화."""
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in [*path_item.get("parameters", []), *op.get("parameters", [])]:
        param = resolve(spec, raw)
        schema = resolve(spec, param["schema"])
        if "anyOf" in schema:  # Optional[...]
            schema = next(resolve(spec, n) for n in schema["anyOf"] if resolve(spec, n).get("type") != "null")
        result[(param["name"], param["in"])] = {
            "required": bool(param.get("required", False)),
            **{k: schema[k] for k in ("type", "format", "minimum", "maximum") if k in schema},
            "default": param["schema"].get("default", schema.get("default")),
        }
    return result


@pytest.mark.parametrize("operation_id", ALL_OPERATIONS)
class TestOperationMatchesContract:
    def test_path_and_method(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        c_path, c_method, _ = operations(contract)[operation_id]
        assert operation_id in operations(app_spec), f"{operation_id} 가 앱에 없어요"
        a_path, a_method, _ = operations(app_spec)[operation_id]
        assert (a_path, a_method) == (c_path, c_method)

    def test_status_codes(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        _, _, c_op = operations(contract)[operation_id]
        _, _, a_op = operations(app_spec)[operation_id]
        c_ok, c_err = codes(c_op)
        a_ok, a_err = codes(a_op)
        assert a_ok == c_ok, "성공 상태 코드"
        assert a_err == c_err, "오류 상태 코드"

    def test_security(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        _, _, c_op = operations(contract)[operation_id]
        _, _, a_op = operations(app_spec)[operation_id]

        def schemes(op: dict[str, Any]) -> set[str]:
            return {name for req in op.get("security", []) for name in req}

        assert schemes(a_op) == schemes(c_op)

    def test_request_shape(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        _, _, c_op = operations(contract)[operation_id]
        _, _, a_op = operations(app_spec)[operation_id]
        c_schema, a_schema = json_schema(c_op), json_schema(a_op)
        assert (c_schema is None) == (a_schema is None)
        if c_schema:
            assert shape(app_spec, a_schema) == shape(contract, c_schema)
            assert required(app_spec, a_schema) == required(contract, c_schema)

    def test_success_response_shape(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        _, _, c_op = operations(contract)[operation_id]
        _, _, a_op = operations(app_spec)[operation_id]
        for code in codes(c_op)[0]:
            c_schema, a_schema = json_schema(c_op, code), json_schema(a_op, code)
            assert (c_schema is None) == (a_schema is None), code
            if c_schema:
                assert shape(app_spec, a_schema) == shape(contract, c_schema)

    def test_path_and_query_parameters(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        c_path, _, c_op = operations(contract)[operation_id]
        a_path, _, a_op = operations(app_spec)[operation_id]
        c_params = parameters(contract, contract["paths"][c_path], c_op)
        a_params = parameters(app_spec, app_spec["paths"][a_path], a_op)
        assert set(a_params) == set(c_params)
        for key, expected in c_params.items():
            actual = a_params[key]
            for field in ("required", "type", "format", "minimum", "maximum"):
                assert actual.get(field) == expected.get(field), f"{key}: {field}"
            if expected["default"] is not None:
                assert actual["default"] == expected["default"], f"{key}: default"

    def test_error_responses_use_api_error_body(self, contract, app_spec, operation_id) -> None:  # type: ignore[no-untyped-def]
        _, _, a_op = operations(app_spec)[operation_id]
        for code in codes(a_op)[1]:
            schema = json_schema(a_op, code)
            assert schema is not None and schema["$ref"].endswith("/ApiErrorBody"), code


def test_api_error_body_shape_matches(contract, app_spec) -> None:  # type: ignore[no-untyped-def]
    c = shape(contract, {"$ref": "#/components/schemas/ApiErrorBody"})
    a = shape(app_spec, {"$ref": "#/components/schemas/ApiErrorBody"})
    assert set(a) == set(c)


def test_security_schemes_are_declared_with_contract_names(contract, app_spec) -> None:  # type: ignore[no-untyped-def]
    assert {"tableBearer", "adminBearer"} <= set(app_spec["components"]["securitySchemes"])
    for name in ("tableBearer", "adminBearer"):
        assert app_spec["components"]["securitySchemes"][name]["scheme"] == "bearer"


class TestRealResponsesCarryContractRequiredFields:
    def _assert_required(self, contract: dict[str, Any], schema_name: str, payload: Any) -> None:
        ref = {"$ref": f"#/components/schemas/{schema_name}"}
        need = required(contract, ref)
        items = payload if isinstance(payload, list) else [payload]
        assert items
        for item in items:
            assert need <= set(item), f"{schema_name}: 누락 {need - set(item)}"

    def test_login_and_menu_responses(self, contract, client: TestClient) -> None:  # type: ignore[no-untyped-def]
        t = client.post("/api/customer/auth/login", json={"storeId": STORE_ID, "tableNumber": 1, "password": TABLE_PASSWORD})
        self._assert_required(contract, "TableTokenResponse", t.json())
        admin = login_admin(client)
        a = client.post("/api/admin/auth/login", json={"storeId": STORE_ID, "username": "admin", "password": "admin1234"})
        self._assert_required(contract, "TokenResponse", a.json())

        menus = client.get("/api/admin/menus", headers=bearer(admin)).json()
        self._assert_required(contract, "CategoryMenus", menus)
        self._assert_required(contract, "Menu", [m for g in menus for m in g["menus"]])
        customer = client.get("/api/customer/menus", headers=bearer(login_table(client))).json()
        self._assert_required(contract, "CategoryMenus", customer)

        body = {"name": "신메뉴", "price": 5000, "description": "", "category": "분식", "imageUrl": None}
        created = client.post("/api/admin/menus", json=body, headers=bearer(admin))
        self._assert_required(contract, "Menu", created.json())
        updated = client.put(f"/api/admin/menus/{created.json()['id']}", json=body, headers=bearer(admin))
        self._assert_required(contract, "Menu", updated.json())

    def test_order_and_table_responses(self, contract, client: TestClient) -> None:  # type: ignore[no-untyped-def]
        admin, table = bearer(login_admin(client)), bearer(login_table(client))
        payload = {
            "clientOrderId": str(uuid.uuid4()),
            "items": [{"menuId": 1, "quantity": 2}, {"menuId": 6, "quantity": 1}],
            "clientTotal": 19000,
        }
        created = client.post("/api/customer/orders", json=payload, headers=table)
        replay = client.post("/api/customer/orders", json=payload, headers=table)
        assert (created.status_code, replay.status_code) == (201, 200)
        self._assert_required(contract, "Order", [created.json(), replay.json()])
        self._assert_required(contract, "OrderItem", created.json()["items"])

        page = client.get("/api/customer/orders", headers=table).json()
        self._assert_required(contract, "OrderPage", page)
        self._assert_required(contract, "Order", page["items"])

        order_id = created.json()["id"]
        board = client.get("/api/admin/dashboard", headers=admin).json()
        self._assert_required(contract, "TableSummary", board)
        self._assert_required(contract, "Order", board[0]["orders"])
        self._assert_required(contract, "Order", client.get(f"/api/admin/orders/{order_id}", headers=admin).json())
        changed = client.patch(f"/api/admin/orders/{order_id}/status", json={"status": "PREPARING"}, headers=admin)
        self._assert_required(contract, "Order", changed.json())

        registered = client.post("/api/admin/tables", json={"tableNumber": 9, "password": "1234"}, headers=admin)
        self._assert_required(contract, "TableInfo", registered.json())
        self._assert_required(contract, "TableInfo", client.get("/api/admin/tables", headers=admin).json())

        extra = client.post("/api/customer/orders", json={**payload, "clientOrderId": str(uuid.uuid4())}, headers=table).json()
        deleted = client.delete(f"/api/admin/orders/{extra['id']}", headers=admin)
        self._assert_required(contract, "TableSummary", deleted.json())

        ended = client.post(f"/api/admin/tables/{created.json()['tableId']}/end-session", headers=admin)
        self._assert_required(contract, "SessionSummary", ended.json())
        history = client.get(f"/api/admin/tables/{created.json()['tableId']}/history", headers=admin).json()
        self._assert_required(contract, "HistoryOrder", history)
        self._assert_required(contract, "OrderItem", history[0]["items"])

    def test_sse_event_payload_matches_server_event(self, contract) -> None:  # type: ignore[no-untyped-def]
        import json

        schema = contract["components"]["schemas"]["ServerEvent"]
        enum = set(schema["properties"]["type"]["enum"])
        for event_type in sorted(enum):
            frame = format_sse(ServerEvent(type=event_type, table_id=None if event_type == "menu_changed" else 1, payload={}))
            data = json.loads(frame.split("\n")[1].removeprefix("data: "))
            assert set(schema["required"]) <= set(data)
            assert data["type"] == event_type and frame.startswith(f"event: {event_type}\n")

    def test_order_error_bodies_use_contract_codes_and_detail_keys(self, contract, client: TestClient) -> None:  # type: ignore[no-untyped-def]
        allowed_codes = set(contract["components"]["schemas"]["ErrorCode"]["enum"])
        allowed_keys = set(contract["components"]["schemas"]["ApiErrorBody"]["properties"])
        detail_props = contract["components"]["schemas"]["ApiErrorBody"]["properties"]["details"]["properties"]
        admin, table = bearer(login_admin(client)), bearer(login_table(client))

        def order(items: list[dict[str, int]], total: int) -> Any:
            return client.post(
                "/api/customer/orders",
                json={"clientOrderId": str(uuid.uuid4()), "items": items, "clientTotal": total},
                headers=table,
            )

        client.delete("/api/admin/menus/2", headers=admin)
        responses = {
            "MENU_UNAVAILABLE": order([{"menuId": 2, "quantity": 1}], 8500),
            "PRICE_CHANGED": order([{"menuId": 1, "quantity": 1}], 1),
            "VALIDATION_ERROR": order([], 0),
            "NO_ACTIVE_SESSION": client.post("/api/admin/tables/1/end-session", headers=admin),
            "DUPLICATE_TABLE": client.post("/api/admin/tables", json={"tableNumber": 1, "password": "1234"}, headers=admin),
            "NOT_FOUND": client.get("/api/admin/orders/999", headers=admin),
            "UNAUTHORIZED": client.get("/api/admin/dashboard"),
        }
        order_id = order([{"menuId": 1, "quantity": 1}], 9000).json()["id"]
        responses["INVALID_TRANSITION"] = client.patch(
            f"/api/admin/orders/{order_id}/status", json={"status": "COMPLETED"}, headers=admin
        )
        for expected, res in responses.items():
            body = res.json()
            assert body["code"] == expected and body["code"] in allowed_codes, body
            assert set(body) <= allowed_keys, body
            assert set(body.get("details", {})) <= set(detail_props), body
        assert set(responses["PRICE_CHANGED"].json()["details"]["currentPrices"][0]) == {"menuId", "price"}

    def test_error_bodies_use_contract_error_codes_and_keys(self, contract, client: TestClient) -> None:  # type: ignore[no-untyped-def]
        allowed_codes = set(contract["components"]["schemas"]["ErrorCode"]["enum"])
        allowed_keys = set(contract["components"]["schemas"]["ApiErrorBody"]["properties"])
        responses = [
            client.post("/api/admin/auth/login", json={"storeId": STORE_ID, "username": "admin", "password": "bad"}),
            client.post("/api/admin/auth/login", json={}),
            client.get("/api/admin/menus"),
            client.delete("/api/admin/menus/999", headers=bearer(login_admin(client))),
            client.get("/api/nope"),
        ]
        for _ in range(5):  # 잠금(429)까지
            responses.append(client.post("/api/admin/auth/login", json={"storeId": STORE_ID, "username": "admin", "password": "bad"}))
        assert 429 in {r.status_code for r in responses}
        for res in responses:
            body = res.json()
            assert body["code"] in allowed_codes, body
            assert set(body) <= allowed_keys, body
