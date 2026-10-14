"""설계 13절 통합 시나리오: 실제 서버(uvicorn)에 HTTP + SSE로 주문부터 이용 완료까지 한 흐름을 확인한다.

프론트엔드 real 모드가 보내는 요청과 같은 경로/본문을 사용한다 (브라우저 조작은 포함하지 않는다).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from tests.conftest import STORE_ID
from tests.live import Live, SseReader


def sse_event(reader: SseReader, timeout: float = 2.0) -> tuple[str, dict]:
    frame = reader.event(timeout=timeout)
    assert frame is not None, "이벤트를 받지 못했어요"
    lines = frame.split("\n")
    data = json.loads(lines[1].removeprefix("data: "))
    return data["type"], data


def test_full_day_scenario(live: Live, clock) -> None:  # type: ignore[no-untyped-def]
    http = live.http
    admin = {"Authorization": f"Bearer {live.admin_token()}"}

    # 1. 관리자 대시보드 + SSE 연결: 테이블 5개, 주문 없음
    board = http.get("/api/admin/dashboard", headers=admin).json()
    assert [t["tableNumber"] for t in board] == [1, 2, 3, 4, 5]
    assert all(not t["sessionActive"] and t["orders"] == [] for t in board)
    stream = SseReader(live.base_url, admin["Authorization"].removeprefix("Bearer "))
    try:
        assert stream.frame() == ": connected"

        # 2. 테이블 6 등록 -> 목록에 비활성으로 나타나고 즉시 태블릿 로그인 가능
        assert http.post("/api/admin/tables", json={"tableNumber": 6, "password": "6060"}, headers=admin).status_code == 201
        listing = http.get("/api/admin/tables", headers=admin).json()
        assert [(t["tableNumber"], t["sessionActive"]) for t in listing][-1] == (6, False)
        assert live.http.post(
            "/api/customer/auth/login", json={"storeId": STORE_ID, "tableNumber": 6, "password": "6060"}
        ).status_code == 200

        # 3. 고객: 테이블 1 로그인 -> 메뉴 조회 -> 주문
        table = {"Authorization": f"Bearer {live.table_token(1)}"}
        menus = http.get("/api/customer/menus", headers=table).json()
        kimchi = menus[0]["menus"][0]
        assert kimchi["name"] == "김치찌개"
        client_order_id = str(uuid.uuid4())
        payload = {
            "clientOrderId": client_order_id,
            "items": [{"menuId": kimchi["id"], "quantity": 2}],
            "clientTotal": kimchi["price"] * 2,
        }
        created = http.post("/api/customer/orders", json=payload, headers=table)
        assert created.status_code == 201
        order = created.json()
        assert order["orderNumber"] == str(order["id"]).zfill(4) and order["status"] == "PENDING"

        # 4. 관리자에게 신규 주문 이벤트 (2초 이내)
        assert sse_event(stream) == ("order_created", {"type": "order_created", "tableId": order["tableId"], "payload": {"orderId": order["id"]}})
        board = http.get("/api/admin/dashboard", headers=admin).json()
        assert (board[0]["orderCount"], board[0]["totalAmount"], board[0]["sessionActive"]) == (1, 18000, True)

        # 5. 상태 변경: 준비 시작 -> 완료 (고객 내역이 반영) / 건너뛰기는 거부
        assert http.patch(f"/api/admin/orders/{order['id']}/status", json={"status": "COMPLETED"}, headers=admin).status_code == 409
        for status in ("PREPARING", "COMPLETED"):
            assert http.patch(f"/api/admin/orders/{order['id']}/status", json={"status": status}, headers=admin).status_code == 200
            kind, data = sse_event(stream)
            assert kind == "order_status_changed" and data["payload"] == {"orderId": order["id"], "status": status}
        mine = http.get("/api/customer/orders", headers=table).json()
        assert [(o["id"], o["status"]) for o in mine["items"]] == [(order["id"], "COMPLETED")]

        # 6. 네트워크 재시도: 같은 clientOrderId -> 200, 주문은 1건 유지, 이벤트 없음
        again = http.post("/api/customer/orders", json=payload, headers=table)
        assert again.status_code == 200 and again.json() == {**order, "status": "COMPLETED"}  # 현재 상태의 같은 주문
        assert len(http.get("/api/customer/orders", headers=table).json()["items"]) == 1
        assert stream.event(timeout=0.5) is None

        # 7. 가격 변경 -> 이전 가격 주문은 PRICE_CHANGED, 갱신된 가격으로 성공
        update = {k: kimchi[k] for k in ("name", "description", "category", "imageUrl")} | {"price": 10000}
        assert http.put(f"/api/admin/menus/{kimchi['id']}", json=update, headers=admin).status_code == 200
        assert sse_event(stream)[0] == "menu_changed"
        stale = http.post("/api/customer/orders", json={**payload, "clientOrderId": str(uuid.uuid4())}, headers=table)
        assert stale.status_code == 409 and stale.json()["code"] == "PRICE_CHANGED"
        assert stale.json()["details"]["currentPrices"] == [{"menuId": kimchi["id"], "price": 10000}]
        fresh_payload = {**payload, "clientOrderId": str(uuid.uuid4()), "clientTotal": 20000}
        fresh = http.post("/api/customer/orders", json=fresh_payload, headers=table)
        assert fresh.status_code == 201 and fresh.json()["totalAmount"] == 20000
        assert sse_event(stream)[0] == "order_created"

        # 8. 주문 삭제 -> 합계 재계산, 이용 완료 -> 합계 0 / 고객 내역 비움 / 과거 내역으로 이동
        deleted = http.delete(f"/api/admin/orders/{fresh.json()['id']}", headers=admin)
        assert deleted.status_code == 200 and (deleted.json()["orderCount"], deleted.json()["totalAmount"]) == (1, 18000)
        assert sse_event(stream)[0] == "order_deleted"

        clock.now = datetime(2026, 10, 14, 14, 59, 59, tzinfo=timezone.utc)  # 한국 시간 10-14 23:59:59
        ended = http.post(f"/api/admin/tables/{order['tableId']}/end-session", headers=admin)
        assert ended.status_code == 200
        assert (ended.json()["archivedOrderCount"], ended.json()["archivedTotalAmount"]) == (1, 18000)
        assert sse_event(stream) == (
            "session_ended",
            {"type": "session_ended", "tableId": order["tableId"], "payload": {"archivedOrderCount": 1}},
        )
        assert http.get("/api/customer/orders", headers=table).json()["items"] == []
        board = http.get("/api/admin/dashboard", headers=admin).json()[0]
        assert (board["sessionActive"], board["totalAmount"], board["orderCount"]) == (False, 0, 0)
        assert http.post(f"/api/admin/tables/{order['tableId']}/end-session", headers=admin).json()["code"] == "NO_ACTIVE_SESSION"

        history_url = f"/api/admin/tables/{order['tableId']}/history"
        history = http.get(history_url, headers=admin).json()
        assert [h["orderId"] for h in history] == [order["id"]]
        assert history[0]["orderNumber"] == order["orderNumber"] and history[0]["totalAmount"] == 18000
        assert history[0]["completedAt"] == "2026-10-14T14:59:59Z"
        assert len(http.get(history_url, params={"from": "2026-10-14", "to": "2026-10-14"}, headers=admin).json()) == 1
        assert http.get(history_url, params={"from": "2026-10-15"}, headers=admin).json() == []

        # 9. 이용 완료 후 첫 주문은 새 세션으로 시작
        again_new = http.post(
            "/api/customer/orders",
            json={**fresh_payload, "clientOrderId": str(uuid.uuid4())},
            headers=table,
        )
        assert again_new.status_code == 201 and again_new.json()["sessionId"] != order["sessionId"]
        assert sse_event(stream)[0] == "order_created"
        # 이전 주문 번호와 겹치지 않는다
        assert again_new.json()["orderNumber"] != order["orderNumber"]
    finally:
        stream.close()
