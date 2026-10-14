# Domain Entities - backend-order (Unit 3)

저장소는 backend-core와 같은 SQLite 파일이다. 시각은 UTC ISO 8601 문자열(`2026-10-14T05:00:00Z`, 초 단위)로 `TEXT`에 저장하고, 금액은 원 단위 `INTEGER`다. 이 Unit은 스키마 모듈 `order` (v1)을 `register_schema`로 등록해 `core` 다음에 적용한다.

소유 테이블: `table_sessions`, `orders`, `order_items`, `order_history`, `order_history_items`. 이미 있는 `tables`(core 소유)는 읽기와 INSERT(등록)만 한다.

확정 답변: `backend-order-functional-design-plan.md` Q1~Q7 (전부 위임 -> AI 추천)과 가정 G1~G19, 추가 G20~G22.

---

## 1. 스키마

### 1.1 table_sessions
테이블 한 번의 이용 기간. 첫 주문 때 만들어지고 "이용 완료"로 닫힌다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | TEXT | PK | `sess_` + 무작위 12자리 소문자 16진수 (예: `sess_3fa91c07b2de`) |
| table_id | INTEGER | NOT NULL, FK -> tables(id) | |
| started_at | TEXT | NOT NULL | 첫 주문 시각 |
| ended_at | TEXT | NULL | NULL이면 활성 세션. 이용 완료 시각 |

- `UNIQUE INDEX ux_sessions_active ON table_sessions(table_id) WHERE ended_at IS NULL` - 테이블당 활성 세션은 최대 1개.
- `INDEX ix_sessions_table ON table_sessions(table_id, started_at)`
- 세션 ID가 충돌하면(PK 위반) 새 ID로 한 번 더 시도한다. 확률은 사실상 없지만 오류로 이어지지 않게 한다.
- 닫힌 세션 행은 지우지 않는다 (이력의 `session_id`가 참조).

### 1.2 orders (현재 세션의 주문)
이용 완료 전의 주문만 있다. 이용 완료 시 `order_history`로 옮기고 이 테이블에서 지운다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 주문 ID. 삭제/이관 후에도 재사용하지 않음 |
| session_id | TEXT | NOT NULL, FK -> table_sessions(id) | |
| table_id | INTEGER | NOT NULL, FK -> tables(id) | 조회 편의를 위한 중복 저장 |
| client_order_id | TEXT | NOT NULL | 클라이언트가 만든 UUID (소문자 정규형) |
| status | TEXT | NOT NULL DEFAULT `PENDING`, CHECK in (`PENDING`,`PREPARING`,`COMPLETED`) | |
| total_amount | INTEGER | NOT NULL, CHECK > 0 | 주문 시점에 서버가 계산한 합계. 주문은 수정되지 않으므로 불변 |
| created_at | TEXT | NOT NULL | |

- `UNIQUE (table_id, client_order_id)` - 멱등성 키.
- `INDEX ix_orders_session ON orders(session_id, id)`
- 주문 번호(`orderNumber`)는 저장하지 않고 `id`에서 계산한다 (3.1절).

### 1.3 order_items
주문 시점의 메뉴 이름/가격 스냅샷. `menus`에 외래키가 없다 (메뉴 소프트 삭제/가격 변경과 독립).

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 입력 순서 = id 오름차순 |
| order_id | INTEGER | NOT NULL, FK -> orders(id) ON DELETE CASCADE | |
| menu_id | INTEGER | NOT NULL | 참고용 (FK 없음) |
| menu_name | TEXT | NOT NULL | 주문 시점의 이름 |
| quantity | INTEGER | NOT NULL, CHECK 1..20 | |
| unit_price | INTEGER | NOT NULL, CHECK > 0 | 주문 시점의 서버 가격 |

- `INDEX ix_order_items_order ON order_items(order_id)`
- 한 주문 안에서 `menu_id`는 중복되지 않는다 (서비스에서 422로 막음).

### 1.4 order_history (이용 완료된 주문)
Q1=A. 이용 완료 시 `orders`에서 **같은 ID로** 복사된 뒤 `orders`에서 삭제된다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| order_id | INTEGER | PK | 원래 `orders.id` (재사용되지 않으므로 충돌 없음) |
| session_id | TEXT | NOT NULL, FK -> table_sessions(id) | 세션 단위 그룹화 |
| table_id | INTEGER | NOT NULL, FK -> tables(id) | |
| client_order_id | TEXT | NOT NULL | 이관 후 재전송 방지용 |
| status | TEXT | NOT NULL | 이관 시점의 상태 (그대로 보존) |
| total_amount | INTEGER | NOT NULL | |
| created_at | TEXT | NOT NULL | 주문 시각 |
| completed_at | TEXT | NOT NULL | 이용 완료(세션 종료) 시각. 같은 세션의 주문은 모두 같은 값 |

- `UNIQUE (table_id, client_order_id)`
- `INDEX ix_history_table_completed ON order_history(table_id, completed_at DESC, order_id DESC)`
- `INDEX ix_history_session ON order_history(session_id)`

### 1.5 order_history_items

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 원래 항목 순서 보존 (이관 시 `order_items.id` 오름차순으로 삽입) |
| order_id | INTEGER | NOT NULL, FK -> order_history(order_id) ON DELETE CASCADE | |
| menu_id | INTEGER | NOT NULL | |
| menu_name | TEXT | NOT NULL | |
| quantity | INTEGER | NOT NULL | |
| unit_price | INTEGER | NOT NULL | |

- `INDEX ix_history_items_order ON order_history_items(order_id)`

### 1.6 관계

```
tables 1 --- * table_sessions 1 --- * orders 1 --- * order_items
                      |
                      +--- * order_history 1 --- * order_history_items
```
(한 주문은 `orders` 또는 `order_history` 중 한 곳에만 있다.)

### 1.7 불변식
1. 테이블당 `ended_at IS NULL`인 세션은 0개 또는 1개.
2. `orders`의 모든 행은 활성 세션에 속한다 (`session.ended_at IS NULL`). 닫힌 세션에는 `orders` 행이 없다.
3. `orders.total_amount = SUM(order_items.quantity * order_items.unit_price)`. 이관 후에도 같다.
4. 한 `(table_id, client_order_id)`는 `orders`와 `order_history`를 합쳐 최대 한 번만 나타난다.
5. 주문 ID는 시스템 전체에서 유일하며 `orders`와 `order_history`에 동시에 존재하지 않는다.

---

## 2. 열거형

| 이름 | 값 | 비고 |
|---|---|---|
| OrderStatus | `PENDING`(대기중), `PREPARING`(준비중), `COMPLETED`(완료) | 전이는 `PENDING -> PREPARING -> COMPLETED`만 |
| ServerEvent.type | `order_created`, `order_status_changed`, `order_deleted`, `session_ended`, `menu_changed` | 계약과 동일 |

---

## 3. 파생 값

### 3.1 주문 번호 (Q2=A)
`orderNumber = str(order.id).zfill(4)` 예: id 7 -> `0007`, id 12345 -> `12345`. 저장하지 않고 항상 ID에서 계산한다 (이력으로 옮겨도 같은 값). 삭제된 주문의 번호는 건너뛰어 비어 있을 수 있다. 프론트엔드 가짜 API(`String(id).padStart(4, '0')`)와 같은 규칙이다.

### 3.2 테이블 요약 (TableSummary)
활성 세션이 있을 때:
- `sessionActive = true`
- `orderCount` = 활성 세션의 `orders` 행 수 (모든 상태 포함)
- `totalAmount` = 활성 세션 `orders.total_amount` 합 (모든 상태 포함, 삭제된 주문은 이미 없으므로 자동 제외)
- `orders` = 최신순 일부 (기본 3건, 테이블 필터 시 전체)

활성 세션이 없으면 `sessionActive=false`, `totalAmount=0`, `orderCount=0`, `orders=[]`.

### 3.3 날짜 경계
`TIMEZONE`(기본 `Asia/Seoul`)의 달력 날짜를 기준으로 한다. `from=D1`, `to=D2`이면 `[D1 00:00 현지, (D2+1일) 00:00 현지)`를 UTC로 바꾼 반열린 구간으로 `completed_at`을 비교한다 (저장 문자열 형식이 같아 문자열 비교가 시간순과 일치).

---

## 4. 이벤트 모델

`app/events_port.py`의 `ServerEvent(type, table_id, payload)`를 그대로 쓴다. 전송 JSON은 `{"type", "tableId", "payload"}`.

| type | tableId | payload | 발행 시점 |
|---|---|---|---|
| `order_created` | 주문 테이블 ID | `{orderId}` | 신규 주문 커밋 후 (멱등 재응답에서는 발행하지 않음) |
| `order_status_changed` | 주문 테이블 ID | `{orderId, status}` | 상태 변경 커밋 후 |
| `order_deleted` | 주문 테이블 ID | `{orderId}` | 삭제 커밋 후 |
| `session_ended` | 테이블 ID | `{archivedOrderCount}` | 이용 완료 커밋 후 |
| `menu_changed` | null | `{}` | 메뉴 변경 커밋 후 (backend-core의 MenuService가 발행) |

### EventBroker 모델
| 요소 | 설명 |
|---|---|
| Subscription | 구독 1개. 크기 100의 큐, `closed` 플래그, 종료 사유 |
| `subscribe()` | 새 Subscription 등록 (이벤트 루프 스레드에서 호출) |
| `unsubscribe(sub)` | 등록 해제 (연결 종료 시 항상 호출) |
| `publish(event)` | 어느 스레드에서든 호출 가능, 블로킹 없음. 모든 구독의 큐로 전달 |
| `close_all()` | 서버 종료 시 모든 구독에 종료 신호 |

- 동기 서비스(스레드풀)에서 호출하는 `publish`는 이벤트 루프로 `call_soon_threadsafe`를 통해 넘긴다. 루프가 아직 없거나 이미 닫힌 경우(테스트/종료 중)는 조용히 무시한다.
- 큐가 가득 찬 구독은 이벤트를 쌓지 않고 끊는다 (종료 사유 `overflow`). 클라이언트는 재연결 후 재조회한다.

---

## 5. 서비스 입출력 모델 (계약과 일치)

| 모델 | 필드 | 계약 스키마 |
|---|---|---|
| OrderCreateRequest | clientOrderId(uuid), items[{menuId, quantity}], clientTotal | `OrderCreateRequest` |
| Order | id, orderNumber, tableId, tableNumber, sessionId, createdAt, status, totalAmount, items[{menuId, menuName, quantity, unitPrice}] | `Order` |
| OrderPage | items[Order], page, size, hasNext | `OrderPage` |
| StatusChangeRequest | status | `StatusChangeRequest` |
| TableSummary | tableId, tableNumber, sessionActive, totalAmount, orderCount, orders[Order] | `TableSummary` |
| TableInfo | id, tableNumber, sessionActive | `TableInfo` |
| TableRegisterRequest | tableNumber, password | `TableRegisterRequest` |
| SessionSummary | tableId, endedAt, archivedOrderCount, archivedTotalAmount | `SessionSummary` |
| HistoryOrder | orderId, orderNumber, tableNumber, createdAt, items, totalAmount, completedAt | `HistoryOrder` |
| ServerEvent | type, tableId, payload | `ServerEvent` |

JSON 필드는 camelCase, DB 컬럼은 snake_case다.

---

## 6. 도메인 예외

모두 `AppError`를 상속하고 기존 핸들러 체계로 매핑된다. 기존 `NotFound`, `ValidationFailed`를 재사용한다.

| 예외 | 속성 | HTTP / `code` | 본문 추가 필드 | 메시지 |
|---|---|---|---|---|
| `MenuUnavailable` | menu_ids: list[int] | 409 `MENU_UNAVAILABLE` | `details.menuIds` | 판매하지 않는 메뉴가 있어요. |
| `PriceChanged` | current_prices: list[{menuId, price}] | 409 `PRICE_CHANGED` | `details.currentPrices` | 메뉴 가격이 변경되었어요. |
| `InvalidTransition` | current, requested | 409 `INVALID_TRANSITION` | - | 주문 상태를 해당 순서로 바꿀 수 없어요. |
| `NoActiveSession` | - | 409 `NO_ACTIVE_SESSION` | - | 이용 중인 세션이 없어요. |
| `DuplicateTable` | table_number | 409 `DUPLICATE_TABLE` | - | 이미 등록된 테이블 번호예요. |

---

## 7. 설정 추가

| 키 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `TIMEZONE` | 아니오 | `Asia/Seoul` | 과거 내역 날짜 경계용 IANA 시간대. 잘못된 이름이면 시작을 거부(키 이름만 출력). Windows에는 시간대 데이터가 없어 `tzdata` 패키지를 의존성에 추가한다 |
| `SSE_KEEPALIVE_SECONDS` | 아니오 | 15 | keep-alive 주석 주기 (테스트에서 줄여 사용) |
| `SSE_QUEUE_SIZE` | 아니오 | 100 | 구독자별 큐 크기 |

기존 설정 검증 규칙(양의 정수 등)을 따른다.
