# Business Logic Model - backend-order (Unit 3)

서비스 흐름과 트랜잭션 경계를 정의한다. 규칙의 구체 값은 `business-rules.md`, 스키마는 `domain-entities.md`, backend-core 흐름은 `../../backend-core/functional-design/business-logic-model.md`를 참고한다.

## 1. 구성 요소와 책임

| 컴포넌트 | 책임 |
|---|---|
| OrderService | 주문 생성(멱등, 가격 재계산), 세션 주문 조회, 대시보드, 주문 상세, 상태 전이, 삭제 |
| TableService | 테이블 등록/목록, 세션 시작/종료, 이력 이관, 과거 내역 조회 |
| EventBroker (`events.py`) | 구독 관리, 스레드 안전 발행, 구독자별 큐 |
| 스키마 모듈 `order` (`schema_order.py`) | 5개 테이블 생성 |
| Routers | `customer_orders`, `admin_orders`(대시보드/주문/SSE), `admin_tables` |
| App Entry 변경 | `order` 스키마 등록, EventBroker 생성/연결, 라우터 등록, 종료 시 `close_all()` |

의존: Router -> Service -> (Database, MenuService(읽기), Security, Clock, EventPublisher). 서비스는 HTTP를 모른다. 시각은 주입된 `clock()`을 쓴다.

세션 시작은 주문 생성의 일부이므로 `OrderService`가 같은 트랜잭션 안에서 `TableService.ensure_active_session(conn, table_id, now)`(연결을 받는 내부 메서드)를 호출한다. 세션 종료/이관은 `TableService.end_session`만 한다.

## 2. 시작/종료 흐름

```
앱 생성 (create_app)
  -> (core) Settings, Database, 'core' 스키마 등록
  -> 'order' v1 스키마 등록 (core 다음 순서)
  -> init_schema: 두 모듈 적용
  -> EventBroker 생성
  -> MenuService.set_publisher(broker)           # menu_changed 연결
  -> TableService, OrderService 구성 (publisher=broker)
  -> 라우터 등록 (정적 서빙보다 먼저)
lifespan 시작: broker.attach_loop(현재 이벤트 루프)
lifespan 종료: broker.close_all()                # 열려 있는 SSE 스트림을 끝냄
```

`create_app(event_publisher=...)`로 외부 발행기를 주입하면 그것을 우선한다(테스트용). 기본은 EventBroker.

## 3. 주문 생성 (US-C4.1, C4.2, E1, E2)

```
POST /api/customer/orders   (테이블 토큰: tableId)
  -> 요청 검증 (ValidationFailed -> 422)           # 형식, 수량, 중복 메뉴, 30종 한도
  -> OrderService.create_order(table_id, req)
     [1] 멱등 선조회 (읽기 연결)
         existing = orders 또는 order_history에서 (table_id, client_order_id)
         있으면 -> (existing, created=False) 반환                  # 메뉴/가격 검사 생략
     [2] menus = MenuService.get_active_menus_by_ids(menuIds)    # 별도 읽기, 쓰기 잠금 밖
         missing = 요청 menuId 중 menus에 없는 것
         if missing: MenuUnavailable(menu_ids=missing 오름차순)   # 409
         total = sum(menus[id].price * qty)                       # 서버 현재 가격으로 재계산
         if total != clientTotal:
             PriceChanged(current_prices=요청한 모든 메뉴의 {menuId, price})   # 409
     [3] BEGIN IMMEDIATE
           재확인: 같은 (table_id, client_order_id)가 그새 생겼는지 (orders, order_history)
                   있으면 ROLLBACK -> (existing, created=False)
           session = SELECT 활성 세션 WHERE table_id=? AND ended_at IS NULL
           if none: INSERT table_sessions(id=sess_xxxx, table_id, started_at=now)
           INSERT orders(session_id, table_id, client_order_id, status='PENDING',
                         total_amount=total, created_at=now)
           INSERT order_items ... (요청 순서대로, menu_name/unit_price는 [2]의 값)
         COMMIT
         (UNIQUE 위반 IntegrityError 시: 롤백 후 기존 주문을 읽어 created=False로 반환)
     [4] 커밋 후 publish(order_created {orderId}) - created=True일 때만
  <- 201 Order (신규) | 200 Order (멱등 재응답)
```

- 주문 상세(Order)는 커밋한 값으로 조립한다 (다시 조회하지 않아도 되지만 단순화를 위해 같은 연결에서 읽어도 된다).
- [1]과 [3]의 재확인은 동시에 같은 `clientOrderId`로 들어온 두 요청 중 하나만 주문을 만들게 한다. 멱등성의 최종 보장은 UNIQUE 제약이다.
- [2]와 [3] 사이에 메뉴가 바뀔 수 있다. 이 틈(수 밀리초)은 허용한다. 주문은 [2]에서 확인한 이름/가격으로 저장된다 (business-rules 3.4).

## 4. 현재 세션 주문 내역 (US-C5.1, C5.2)

```
GET /api/customer/orders?page=0&size=10   (테이블 토큰)
  -> 쿼리 검증: page >= 0, 1 <= size <= 50 (위반 시 422)
  -> OrderService.list_session_orders(table_id, page, size)
       세션 = 활성 세션 (없으면 -> 빈 페이지 {items: [], page, size, hasNext: false})
       rows = SELECT orders WHERE session_id=? ORDER BY id DESC LIMIT size+1 OFFSET page*size
       hasNext = len(rows) > size; rows = rows[:size]
       항목을 한 번의 IN 쿼리로 가져와 조립
  <- 200 OrderPage
```
고객 폴링(5초)은 쓰기 잠금 없이 읽기 연결만 쓴다.

## 5. 대시보드 (US-A2.1, A2.5)

```
GET /api/admin/dashboard[?table=<tableNumber>]   (관리자 토큰)
  -> table 파라미터가 있으면 정수 >= 1 (위반 422)
  -> OrderService.dashboard(table_number | None)
       tables = 전체 테이블 (번호 오름차순). table_number가 있으면 그 번호 하나, 없으면 NotFound(404)
       활성 세션 = table_sessions WHERE ended_at IS NULL (테이블들에 대해 한 번에)
       집계 = 활성 세션별 COUNT(*), SUM(total_amount) (한 쿼리)
       주문 = limit(None이면 테이블당 최신 3건, 지정이면 전체) ORDER BY id DESC
       항목은 한 번의 IN 쿼리로 가져와 조립 (테이블 수만큼 쿼리를 반복하지 않음)
  <- 200 TableSummary[]
```
- `table`을 지정하면 결과는 항상 요소 1개의 배열이다. `totalAmount`/`orderCount`는 필터와 무관하게 활성 세션 전체 기준이다.
- 읽기 중 변경이 끼어들 수 있으므로 한 읽기 연결에서 `BEGIN`(deferred)으로 일관된 스냅샷을 쓴다 (WAL 읽기 트랜잭션).

## 6. 주문 상세 (US-A2.3)

```
GET /api/admin/orders/{orderId}   (관리자 토큰)
  -> OrderService.get_order(order_id)
       orders에서 조회 (없거나 이력으로 이관된 주문이면 NotFound)
  <- 200 Order
```

## 7. 주문 상태 변경 (US-A2.4, E5)

```
PATCH /api/admin/orders/{orderId}/status   { status }
  -> 요청 검증: status가 enum이 아니면 422 (fields.status)
  -> OrderService.change_status(order_id, new_status)
       BEGIN IMMEDIATE
         row = SELECT id, table_id, status FROM orders WHERE id=?   (없으면 NotFound)
         if NEXT[row.status] != new_status: InvalidTransition       # 409
         UPDATE orders SET status=new WHERE id=? AND status=row.status
         if rowcount != 1: InvalidTransition                        # 방어적 확인
       COMMIT
       publish(order_status_changed {orderId, status}, tableId)
  <- 200 Order
```
`NEXT = {PENDING: PREPARING, PREPARING: COMPLETED}` (COMPLETED의 다음은 없음). 같은 상태 요청, 건너뛰기, 되돌리기는 모두 409다. 오류(404/409)일 때는 이벤트를 발행하지 않는다.

## 8. 주문 삭제 (US-A3.2, E8)

```
DELETE /api/admin/orders/{orderId}
  -> OrderService.delete_order(order_id)
       BEGIN IMMEDIATE
         row = SELECT id, table_id, total_amount FROM orders WHERE id=?   (없으면 NotFound)
         DELETE FROM orders WHERE id=?        # order_items는 CASCADE
         summary = 같은 연결에서 해당 테이블의 TableSummary 계산 (기본 최신 3건)
       COMMIT
       로그: "order deleted id=.. table=.. amount=.." (INFO)
       publish(order_deleted {orderId}, tableId)
  <- 200 TableSummary
```
- 한 트랜잭션이므로 실패하면 아무것도 바뀌지 않는다 (US-E8). 응답의 요약은 삭제가 반영된 값이다.
- 마지막 주문을 삭제해도 세션은 유지된다 (`sessionActive=true`, 합계 0). 다음 이용 완료로만 닫힌다.

## 9. 테이블 등록 / 목록 (US-A3.1)

등록:
```
POST /api/admin/tables   { tableNumber, password }
  -> 요청 검증 (422): tableNumber 정수 1..999, password ^\d{4}$ (core와 같은 문구)
  -> TableService.register(table_number, password)
       hash = bcrypt(password)                 # 트랜잭션 밖에서 계산 (수백 ms)
       BEGIN IMMEDIATE
         INSERT INTO tables(table_number, password_hash, created_at)
         (UNIQUE 위반 IntegrityError -> DuplicateTable)
       COMMIT
  <- 201 TableInfo(id, tableNumber, sessionActive=false)
```
목록:
```
GET /api/admin/tables
  -> TableService.list_tables()
       SELECT t.*, EXISTS(활성 세션) FROM tables ORDER BY table_number
  <- 200 TableInfo[]
```
등록된 테이블은 즉시 `customerLogin`으로 로그인할 수 있다 (core가 `tables`를 직접 읽음). 이벤트는 발행하지 않는다 (대시보드는 다음 재조회에서 반영. 프론트엔드가 등록 성공 시 직접 재조회).

## 10. 이용 완료 (US-A3.3, E8)

```
POST /api/admin/tables/{tableId}/end-session
  -> TableService.end_session(table_id)
       table 존재 확인 (없으면 NotFound)
       BEGIN IMMEDIATE
         session = 활성 세션 WHERE table_id=?   (없으면 ROLLBACK -> NoActiveSession)
         now = clock()
         INSERT INTO order_history(order_id, session_id, table_id, client_order_id, status,
                                   total_amount, created_at, completed_at)
           SELECT id, session_id, table_id, client_order_id, status, total_amount, created_at, :now
           FROM orders WHERE session_id=:sid
         INSERT INTO order_history_items(order_id, menu_id, menu_name, quantity, unit_price)
           SELECT oi.order_id, oi.menu_id, oi.menu_name, oi.quantity, oi.unit_price
           FROM order_items oi JOIN orders o ON o.id = oi.order_id
           WHERE o.session_id=:sid ORDER BY oi.id
         archived_count, archived_total = 이관한 행 수, 합계
         DELETE FROM orders WHERE session_id=:sid          # order_items는 CASCADE
         UPDATE table_sessions SET ended_at=:now WHERE id=:sid
       COMMIT
       publish(session_ended {archivedOrderCount}, tableId)
  <- 200 SessionSummary(tableId, endedAt=now, archivedOrderCount, archivedTotalAmount)
```
- 어느 단계든 실패하면 전체 롤백되어 주문은 현재 목록에 그대로 남고 세션은 유지된다.
- 주문이 0건인 활성 세션도 정상적으로 닫는다 (`archivedOrderCount=0`).
- 이용 완료 직후 같은 테이블의 첫 주문이 새 세션을 만든다.
- 이관 전후 합계가 같아야 한다: `archived_total == SUM(이관 전 orders.total_amount)`. 코드는 INSERT...SELECT 결과 행 수를 DELETE 행 수와 비교해 다르면 예외를 던져 롤백한다.

## 11. 과거 주문 내역 (US-A3.4)

```
GET /api/admin/tables/{tableId}/history[?from=YYYY-MM-DD][&to=YYYY-MM-DD]
  -> 파라미터 검증: 날짜 형식 위반 422, from > to 면 422 (fields.from)
  -> TableService.get_history(table_id, from, to)
       table 존재 확인 (없으면 NotFound)
       start = from의 현지 자정 -> UTC, end = (to + 1일)의 현지 자정 -> UTC
       rows = SELECT order_history WHERE table_id=? [AND completed_at >= start] [AND completed_at < end]
              ORDER BY completed_at DESC, order_id DESC
       항목은 IN 쿼리로 한 번에 조립
  <- 200 HistoryOrder[]
```
검증 순서: 경로(`tableId` 정수) -> 날짜 형식/순서(422) -> 테이블 존재(404). 페이지네이션은 없다 (MVP, 테이블 하나의 과거 주문 전체. 필터로 범위를 줄임).

## 12. 실시간 이벤트 (US-A2.2, E6)

### 12.1 구독

```
GET /api/admin/events   (관리자 토큰, Authorization 헤더)
  -> require_admin (실패 401, 스트림 열기 전)
  -> 응답 헤더: Content-Type: text/event-stream, Cache-Control: no-cache,
                X-Accel-Buffering: no, Connection: keep-alive
  -> sub = broker.subscribe()
  -> 루프:
       event = sub.queue.get(timeout = keepalive 주기)
         이벤트 -> "event: <type>\ndata: <{type,tableId,payload} JSON 한 줄>\n\n" 전송
         타임아웃 -> ": keep-alive\n\n" 전송
         종료 신호(overflow / 서버 종료) -> 루프 탈출
       토큰 만료 시각(exp)이 지나면 루프 탈출 (G20)
       클라이언트 연결 끊김 감지 -> 루프 탈출
  -> finally: broker.unsubscribe(sub)
```
스트림을 열면 첫 줄로 `: connected\n\n` 주석을 즉시 보내 프록시/브라우저가 연결을 열린 것으로 인식하게 한다 (G21).

### 12.2 발행

```
서비스(스레드풀) --커밋 후--> safe_publish(broker, ServerEvent)
  broker.publish(event):
     loop.call_soon_threadsafe(_dispatch, event)         # 블로킹 없음
  _dispatch (이벤트 루프 스레드):
     for sub in subscribers:
         try: sub.queue.put_nowait(event)
         except QueueFull: sub.close('overflow'); subscribers.remove(sub)
```
- 발행은 항상 커밋 이후이고, 실패해도 요청은 성공한다 (`safe_publish`).
- 느린 구독자는 끊어서 다른 구독자와 서버에 영향을 주지 않는다. 클라이언트는 프론트엔드 규칙(1/2/4/8/10초 재연결 + 재조회)으로 복구한다.
- 이벤트 순서는 한 발행 스레드에서의 호출 순서를 따르며, 서로 다른 요청 간 순서는 보장하지 않는다 (클라이언트는 이벤트를 "재조회 신호"로 사용).

### 12.3 발행 지점 요약

| 동작 | 이벤트 | 소유 |
|---|---|---|
| 주문 생성(신규) | `order_created` | OrderService |
| 상태 변경 | `order_status_changed` | OrderService |
| 주문 삭제 | `order_deleted` | OrderService |
| 이용 완료 | `session_ended` | TableService |
| 메뉴 등록/수정/삭제/순서 | `menu_changed` | MenuService (core, 브로커 연결로 활성화) |

## 13. 통합 시나리오 (최종 검증용)

프론트엔드 `VITE_API_MODE=real` 빌드를 FastAPI가 서빙하는 같은 오리진에서 실행한다.

1. 시드 후 서버 시작, 관리자 로그인 -> 대시보드(테이블 5개, 주문 없음) + SSE 연결됨 표시.
2. 관리자: 테이블 6 등록 -> 목록에 `sessionActive=false`.
3. 고객 태블릿: 테이블 1 로그인 -> 메뉴 조회 -> 장바구니 -> 주문 확정 -> 주문 번호 표시 -> 5초 후 메뉴 복귀.
4. 관리자 대시보드에 2초 이내 새 주문이 강조 표시된다 (`order_created`).
5. 관리자: 준비 시작 -> 완료 처리. 고객 주문 내역이 5초 안에 상태를 반영한다.
6. 같은 `clientOrderId` 재전송(네트워크 재시도) -> 200, 주문 1건 유지.
7. 관리자: 메뉴 가격 수정 -> 고객이 이전 가격으로 주문 시 `PRICE_CHANGED` -> 갱신 후 성공.
8. 관리자: 주문 삭제 -> 합계 재계산. 이용 완료 -> 합계 0, 고객 내역 비어 있음, 과거 내역에 이관됨 (날짜 필터 확인).
9. 이용 완료 후 새 주문 -> 새 세션 ID로 시작.

## 14. 계약 검증 대상 (이 Unit, 11개 operation)

| operation | 경로 | 인증 | 응답 코드 |
|---|---|---|---|
| createOrder | POST /api/customer/orders | table | 201, 200, 401, 409, 422, 500 |
| listSessionOrders | GET /api/customer/orders | table | 200, 401, (422 아래 참고), 500 |
| getDashboard | GET /api/admin/dashboard | admin | 200, 401, 404, (422), 500 |
| getOrder | GET /api/admin/orders/{orderId} | admin | 200, 401, 404, (422), 500 |
| deleteOrder | DELETE /api/admin/orders/{orderId} | admin | 200, 401, 404, (422), 500 |
| changeOrderStatus | PATCH /api/admin/orders/{orderId}/status | admin | 200, 401, 404, 409, 422, 500 |
| streamAdminEvents | GET /api/admin/events | admin | 200, 401, 500 |
| listTables | GET /api/admin/tables | admin | 200, 401, 500 |
| registerTable | POST /api/admin/tables | admin | 201, 401, 409, 422, 500 |
| endSession | POST /api/admin/tables/{tableId}/end-session | admin | 200, 401, 404, 409, (422), 500 |
| getTableHistory | GET /api/admin/tables/{tableId}/history | admin | 200, 401, 404, 422, 500 |

괄호 친 `422`는 경로/쿼리 변수 형식 오류(정수가 아님, `page`/`size`/`table` 범위 위반)에서 구현이 반환한다. backend-core에서 `deleteMenu`가 같은 이유로 계약에 422를 추가한 선례를 따라, 계약 일치 테스트가 발견하는 대로 `contracts/openapi.yaml`에 422를 추가한다 (D4 검증 결과 참고, 프론트엔드 타입 재생성 필요).

## 15. 스토리 반영 확인 (18개)

| 스토리 | 반영 위치 |
|---|---|
| US-C4.1 주문 확인 후 확정 | 3절, BR-2, BR-3 |
| US-C4.2 주문 성공 확인 | 3절 (201 + `orderNumber`), BR-1.1 |
| US-C5.1 현재 세션 주문 내역 | 4절, BR-6.1 |
| US-C5.2 주문 상태 자동 갱신 | 4절 (읽기 전용 폴링 대상), 7절 |
| US-A2.1 테이블별 대시보드 | 5절, BR-6.2 |
| US-A2.2 신규 주문 실시간 수신 | 12절, 3절 [4], BR-8 |
| US-A2.3 주문 상세 | 6절 |
| US-A2.4 주문 상태 변경 | 7절, BR-4 |
| US-A2.5 테이블별 필터링 | 5절 (`table` 파라미터) |
| US-A3.1 테이블 초기 설정 | 9절, BR-7 |
| US-A3.2 주문 삭제 | 8절, BR-5.1 |
| US-A3.3 이용 완료 | 10절, BR-5.2 |
| US-A3.4 과거 내역 | 11절, BR-6.3 |
| US-E1 주문 실패 시 장바구니 유지 | 3절 (실패 시 부분 저장 없음, 멱등 재전송) |
| US-E2 존재하지 않는 메뉴 | 3절 [2] (`MENU_UNAVAILABLE`), BR-3.2 |
| US-E5 잘못된 상태 전이 | 7절 (`INVALID_TRANSITION`) |
| US-E6 실시간 연결 오류 복구 | 12절 (keep-alive, overflow 종료, 만료 종료), BR-8 |
| US-E8 삭제/이용 완료 실패 피드백 | 8절, 10절 (단일 트랜잭션, `NO_ACTIVE_SESSION`) |

18개 모두 반영됨.
