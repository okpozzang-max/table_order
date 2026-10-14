# Business Rules - backend-order (Unit 3)

확정 답변: `backend-order-functional-design-plan.md` Q1~Q7 (전부 위임 -> AI 추천)과 가정 G1~G19(이견 없음). 이 문서에서 G20~G22를 추가한다.

## 설계 결정 요약

| 항목 | 결정 | 출처 |
|---|---|---|
| 이력 이관 | 별도 `order_history`/`order_history_items`로 복사(주문 ID 유지) 후 `orders`에서 삭제, 한 트랜잭션 | Q1: A |
| 주문 번호 | 주문 ID를 4자리로 채움 (`0007`), 저장하지 않고 계산 | Q2: A |
| 주문 삭제 | 물리 삭제 + 서버 로그 | Q3: A |
| 과거 내역 날짜 필터 | 이용 완료일(`completedAt`) 기준 | Q4: B |
| 날짜 경계 | `Asia/Seoul` 고정(`TIMEZONE`), `tzdata` 추가 | Q5: A |
| 한 주문의 중복 메뉴 | 422 거부 | Q6: A |
| 주문 한도 | 서로 다른 메뉴 최대 30종, 금액 제한 없음 | Q7: A |
| 스키마 | 모듈 `order` v1, 메뉴 FK 없음(이름/가격 스냅샷) | G1 |
| 세션 | 테이블당 활성 1개(부분 유니크), 첫 주문이 생성 | G2 |
| 멱등성 | `(table_id, client_order_id)`, 재전송은 200 | G4 |
| 이벤트 | 커밋 후 발행, 구독자 큐 100, 넘치면 끊음 | G15 |

### 추가 가정
| # | 가정 |
|---|---|
| G20 | SSE 스트림은 연결에 사용한 관리자 토큰의 `exp`가 지나면 서버가 닫는다. 클라이언트는 재연결하다 401을 받아 로그인 화면으로 간다 (만료된 토큰으로 이벤트를 계속 받지 않음). |
| G21 | SSE는 연결 직후 `: connected` 주석을 한 번 보낸다. 이벤트 재전송(Last-Event-ID)과 이벤트 ID는 두지 않는다 (이벤트는 "재조회 신호"이고 재연결 시 클라이언트가 재조회). |
| G22 | 멱등 재응답은 요청 본문이 처음과 달라도(항목/금액 등) 기존 주문을 그대로 반환한다. 본문 비교는 하지 않는다 (클라이언트가 갱신하면 새 `clientOrderId`를 만드는 것이 프론트엔드 규칙). |

---

## 1. 식별자와 형식

### 1.1 주문 번호
- `orderNumber = str(id).zfill(4)`. 시스템 전체에서 유일 (ID가 유일하므로).
- 이력으로 이관돼도 같은 값이다. 삭제로 번호에 빈 구멍이 생길 수 있다.

### 1.2 세션 ID
- `sess_` + 무작위 12자리 16진수 (`secrets.token_hex(6)`). 충돌 시(PK 위반) 한 번 더 시도.

### 1.3 clientOrderId
- UUID 문자열. 소문자 정규형으로 저장/비교한다 (`Uuid` 파싱 후 `str()`). 대소문자만 다른 같은 UUID는 같은 키로 취급.

### 1.4 시각
- 응답/저장 모두 UTC `YYYY-MM-DDTHH:MM:SSZ`. 같은 요청 안에서는 `clock()`을 한 번만 호출한 값을 쓴다 (예: 이용 완료의 모든 `completed_at`, `endedAt`).

---

## 2. 입력 검증 규칙

공통: 모든 필드 오류를 모아 한 번에 422 `VALIDATION_ERROR`(`fields`)로 응답한다. 타입이 틀린 입력(문자열 수량 등)도 같은 방식으로 변환한다.

| 대상 | 필드 | 규칙 | 오류 문구 (`fields[필드]`) |
|---|---|---|---|
| 주문 생성 | clientOrderId | 유효한 UUID | 주문 식별자 형식이 올바르지 않아요. |
| | items | 1개 이상 | 주문할 메뉴를 선택해주세요. |
| | items | 서로 다른 메뉴 30종 이하 | 한 번에 주문할 수 있는 메뉴는 최대 30종류예요. |
| | items | `menuId` 정수(양수), `quantity` 정수 1~20 | 수량은 1~20 사이로 입력해주세요. |
| | items | 같은 `menuId` 중복 없음 | 같은 메뉴는 한 줄로 합쳐서 주문해주세요. |
| | clientTotal | 정수 >= 0 | 주문 금액이 올바르지 않아요. |
| 상태 변경 | status | `PENDING`/`PREPARING`/`COMPLETED` 중 하나 | 주문 상태가 올바르지 않아요. |
| 테이블 등록 | tableNumber | 정수 1~999 | 테이블 번호는 1~999 사이 숫자로 입력해주세요. |
| | password | `^\d{4}$` | 비밀번호는 숫자 4자리입니다. |
| 과거 내역 | from, to | `YYYY-MM-DD` 실제 존재하는 날짜 | 날짜 형식이 올바르지 않아요. (`fields.from` / `fields.to`) |
| | from <= to | 둘 다 있을 때 | 시작일이 종료일보다 늦을 수 없습니다. (`fields.from`) |
| 고객 주문 내역 | page, size | page >= 0, 1 <= size <= 50 | 해당 값의 범위가 올바르지 않아요. (`fields.page` / `fields.size`) |
| 대시보드 | table | 정수 >= 1 | 테이블 번호는 1 이상 숫자로 입력해주세요. (`fields.table`) |
| 경로 변수 | orderId, tableId | 정수 | 형식이 올바르지 않아요. (`fields.orderId` / `fields.tableId`) |

- 항목 안의 문제(수량, 중복, 개수)는 모두 `fields.items`에 표시하며 한 필드에 문구가 여러 개면 첫 번째 위반의 문구를 쓴다.
- 비밀번호 문구와 번호 문구는 프론트엔드/core와 동일하다.
- 검증 순서: 인증(401) -> 요청 형식(422) -> (이후 서비스 단계의 404/409).

---

## 3. 주문 생성 규칙

### 3.1 멱등성
1. `(table_id, client_order_id)`가 `orders`에 있으면 그 주문을 **200**으로 반환한다.
2. `orders`에 없고 `order_history`에 있으면 (재전송 사이에 이용 완료됨) 그 이력의 주문을 200으로 반환한다. 이때 `sessionId`는 원래 세션이다.
3. 재응답에서는 이벤트를 발행하지 않고 어떤 데이터도 바꾸지 않는다.
4. 멱등 확인은 메뉴/가격 검증보다 **먼저** 한다. 즉 처음 성공한 뒤 메뉴가 삭제/가격 변경돼도 재전송은 기존 주문을 돌려준다 (G22).
5. 동시에 같은 키로 두 요청이 오면 한 쪽만 주문을 만들고, 다른 쪽은 UNIQUE 위반/재확인으로 기존 주문을 200으로 받는다 (주문 1건).
6. `clientOrderId`의 유효 범위는 테이블 단위다. 다른 테이블에서 같은 UUID는 별개다.

### 3.2 판매 가능 메뉴 (US-E2)
- 요청의 `menuId` 중 `MenuService.get_active_menus_by_ids` 결과에 없는 것(삭제됨/존재하지 않음)이 하나라도 있으면 409 `MENU_UNAVAILABLE`, `details.menuIds` = 해당 ID들 (오름차순). 이 경우 아무것도 저장하지 않는다. 사용 가능한 항목만 부분 주문하지 않는다.

### 3.3 가격 재계산 (US-C4.1)
- `total = sum(현재 서버 가격 * quantity)`. 클라이언트의 `unitPrice`는 받지 않으며 `clientTotal`은 비교에만 쓴다.
- `total != clientTotal`이면 409 `PRICE_CHANGED`, `details.currentPrices` = **요청한 모든 메뉴**의 `{menuId, price}` (가격이 안 바뀐 메뉴 포함, 요청 순서). 프론트엔드는 이 값으로 장바구니 단가를 갱신한다.
- 검증 순서: 형식(422) -> 멱등(200) -> 판매 불가(409 `MENU_UNAVAILABLE`) -> 합계 불일치(409 `PRICE_CHANGED`). 둘 다 해당되면 `MENU_UNAVAILABLE`이 먼저다 (없는 메뉴의 가격은 알려줄 수 없으므로).

### 3.4 스냅샷과 경쟁 허용 범위
- 항목의 `menu_name`, `unit_price`는 검증에 쓴 값을 그대로 저장한다. 이후 메뉴 수정/삭제는 기존 주문에 영향이 없다.
- 메뉴 검증(별도 읽기)과 주문 저장(쓰기 트랜잭션) 사이에 메뉴가 바뀔 수 있는 아주 짧은 틈은 허용한다. 결과 주문은 검증 시점의 이름/가격으로 일관되게 저장되므로 합계가 어긋나지 않는다.

### 3.5 세션
- 주문 저장 트랜잭션에서 활성 세션을 찾고 없으면 만든다 (`started_at = now`). 이미 있으면 재사용한다.
- 주문은 항상 활성 세션에 속한다. 세션 ID는 응답 `Order.sessionId`로 노출된다.

### 3.6 응답
- 신규: 201, 멱등: 200. 본문은 `Order`(상태 `PENDING`, 항목은 요청 순서, `totalAmount`는 서버 계산값).

---

## 4. 상태 전이 규칙 (US-A2.4, E5)

| 현재 \ 요청 | PENDING | PREPARING | COMPLETED |
|---|---|---|---|
| PENDING | 409 | **허용** | 409 |
| PREPARING | 409 | 409 | **허용** |
| COMPLETED | 409 | 409 | 409 |

- 허용 전이는 `PENDING -> PREPARING`, `PREPARING -> COMPLETED`뿐이다. 같은 상태 재요청, 건너뛰기, 되돌리기는 모두 409 `INVALID_TRANSITION`.
- 검사와 갱신은 한 쓰기 트랜잭션이며 `UPDATE ... WHERE id=? AND status=<읽은 상태>`로 보호한다. 두 관리자가 동시에 같은 전이를 요청하면 한 쪽만 성공하고 다른 쪽은 409.
- 존재하지 않거나 이미 이력으로 이관된 주문은 404 (409보다 우선).
- 성공 시 `order_status_changed {orderId, status}` 발행, 응답은 갱신된 `Order`.
- 고객은 상태를 바꿀 수 없다 (고객 토큰으로 관리자 API 호출 시 401).

---

## 5. 삭제와 이용 완료

### 5.1 주문 삭제 (US-A3.2, E8)
1. 활성 세션의 주문만 삭제할 수 있다. 없거나 이력으로 이관된 주문은 404.
2. 상태와 무관하게 삭제할 수 있다 (`COMPLETED` 포함).
3. 물리 삭제. `order_items`는 CASCADE로 함께 삭제. 한 트랜잭션 안에서 해당 테이블의 갱신된 요약을 계산한다.
4. 삭제한 주문 번호의 `client_order_id`는 사라지므로, 같은 UUID를 재전송하면 새 주문이 만들어질 수 있다 (정상: 삭제는 관리자의 의도적 조치).
5. 서버 로그 INFO에 `order id/table id/total amount/status`를 남긴다 (고객 정보 없음).
6. 응답 `TableSummary`: 삭제 반영 후 `totalAmount`/`orderCount`, `orders`는 최신 3건. 이벤트 `order_deleted`.
7. 마지막 주문을 삭제해도 세션은 유지된다.

### 5.2 이용 완료 (US-A3.3, E8)
1. 테이블이 없으면 404. 활성 세션이 없으면 409 `NO_ACTIVE_SESSION`.
2. 활성 세션이면 주문이 0건이어도 닫는다.
3. 한 트랜잭션에서: 모든 주문과 항목을 이력으로 복사 -> `orders` 삭제 -> 세션 `ended_at = now`. `completed_at = now`이며 같은 세션의 모든 이력 행이 같다.
4. 이관된 행 수와 삭제된 행 수가 다르면 예외로 롤백한다 (데이터 유실 방지).
5. 주문 상태는 그대로 보존한다 (`PENDING`이어도 이관). 완료 처리되지 않은 주문이 있어도 이용 완료는 막지 않는다 (요구사항: 관리자 판단).
6. 응답 `SessionSummary(tableId, endedAt, archivedOrderCount, archivedTotalAmount)`, 이벤트 `session_ended {archivedOrderCount}`.
7. 같은 요청을 연속으로 두 번 보내면 두 번째는 409 `NO_ACTIVE_SESSION` (프론트엔드가 "이미 이용 완료된 테이블이에요."로 처리).
8. 이관 후 고객 주문 내역은 비어 있고 대시보드 합계는 0, `sessionActive=false`.

---

## 6. 조회 규칙

### 6.1 고객 현재 세션 주문 (US-C5.1, C5.2)
- 활성 세션의 주문만. 최신순(`id` 내림차순). 활성 세션이 없으면 빈 페이지 (`items=[]`, `hasNext=false`).
- `page` 0부터, `size` 기본 10 (1~50). `hasNext`는 `size+1`건을 읽어 판단.
- 다른 테이블의 주문은 보이지 않는다 (토큰의 `tableId`로만 조회).

### 6.2 대시보드 (US-A2.1, A2.5)
- 등록된 모든 테이블을 번호 오름차순으로 반환 (주문 없는 테이블 포함).
- `table` 없음: 테이블마다 활성 세션의 최신 3건 `orders`. `table=N`: 해당 번호 테이블 1개와 활성 세션 전체 주문(최신순). 없는 번호는 404.
- `totalAmount`/`orderCount`는 항상 활성 세션 전체 기준 (미리보기 건수와 무관).
- `Order.tableNumber`는 `tables.table_number`에서 가져온다.

### 6.3 과거 내역 (US-A3.4)
- 테이블 1개의 이력만. `completedAt` 내림차순, 같으면 `orderId` 내림차순.
- `from`/`to`는 이용 완료일(`TIMEZONE` 기준 날짜) 포함 구간. 둘 다 선택. 하나만 있으면 한쪽만 제한.
- 필터 결과가 없으면 빈 배열(200). 없는 `tableId`는 404.
- 항목은 이관 당시 순서 그대로.

### 6.4 주문 상세 (US-A2.3)
- 활성 세션의 주문만 (이력 주문은 404). 응답은 `Order`.

---

## 7. 테이블 등록과 목록 (US-A3.1)

1. 번호 1~999, 비밀번호 숫자 4자리 (검증 2절). 앞뒤 공백은 제거 후 검사.
2. 같은 번호가 있으면 409 `DUPLICATE_TABLE`. 중복 확인은 INSERT의 UNIQUE 위반으로 판정 (경쟁 조건 안전).
3. 비밀번호는 bcrypt 해시만 저장 (cost = `BCRYPT_ROUNDS`). 해시 계산은 쓰기 잠금 밖에서 한다.
4. 응답 201 `TableInfo(id, tableNumber, sessionActive=false)`. 비밀번호/해시는 어디에도 반환/로그하지 않는다.
5. 등록 직후 해당 번호/비밀번호로 `customerLogin`이 성공한다 (실패 잠금 집계와는 독립).
6. 수정/삭제 API는 없다 (MVP). 목록은 번호 오름차순, `sessionActive`는 활성 세션 존재 여부.

---

## 8. SSE와 이벤트 규칙 (US-A2.2, E6)

| 항목 | 규칙 |
|---|---|
| 인증 | 관리자 토큰 필수 (Authorization 헤더). 실패하면 스트림을 열지 않고 401 JSON |
| 응답 헤더 | `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` |
| 프레임 | `event: <type>\ndata: <ServerEvent JSON 한 줄>\n\n`. JSON은 줄바꿈이 없는 한 줄 |
| 연결 직후 | `: connected` 주석 1회 (G21) |
| keep-alive | `SSE_KEEPALIVE_SECONDS`(기본 15)마다 `: keep-alive` 주석 |
| 이벤트 종류 | `order_created`, `order_status_changed`, `order_deleted`, `session_ended`, `menu_changed` (payload는 domain-entities 4절) |
| 발행 시점 | 항상 DB 커밋 이후. 롤백/오류 응답이면 발행하지 않음. 발행 오류는 요청을 실패시키지 않음 |
| 구독 범위 | 모든 관리자 구독자가 모든 이벤트를 받는다 (매장 1개) |
| 느린 구독자 | 큐 100이 가득 차면 그 연결만 끊음 (다른 구독자/요청 영향 없음) |
| 종료 | 클라이언트 연결 종료, 서버 종료(`close_all`), 토큰 만료(G20), overflow 시 구독 해제. 해제는 항상 `finally`에서 보장 |
| 전달 지연 | 커밋 후 이벤트가 스트림에 쓰이기까지 1초 이내를 목표로 하며 신규 주문은 2초 이내 도달해야 한다 (테스트로 검증) |
| 재전송 | 없음. 끊겼다 재연결한 클라이언트는 대시보드를 다시 조회한다 |

---

## 9. 오류 매핑 (이 Unit)

| 상황 | HTTP | `code` | 본문 추가 필드 |
|---|---|---|---|
| 요청 형식/범위 위반 | 422 | `VALIDATION_ERROR` | `fields` |
| 토큰 없음/만료/role 불일치 | 401 | `UNAUTHORIZED` | `WWW-Authenticate: Bearer` |
| 주문/테이블 없음, 이관된 주문 | 404 | `NOT_FOUND` | - |
| 판매 불가 메뉴 | 409 | `MENU_UNAVAILABLE` | `details.menuIds` |
| 합계 불일치 | 409 | `PRICE_CHANGED` | `details.currentPrices` |
| 허용되지 않는 전이 | 409 | `INVALID_TRANSITION` | - |
| 활성 세션 없음 (이용 완료) | 409 | `NO_ACTIVE_SESSION` | - |
| 테이블 번호 중복 | 409 | `DUPLICATE_TABLE` | - |
| 처리되지 않은 예외 | 500 | `INTERNAL_ERROR` | 내부 정보 비노출 |

- 보호된 모든 엔드포인트에서 인증(401)이 가장 먼저 판정된다 (본문/경로 검증보다 앞).
- 고객 API(`/api/customer/orders`)는 테이블 토큰만, 관리자 API는 관리자 토큰만 받는다.

---

## 10. 보안/무결성 규칙 요약

1. 금액은 항상 서버가 계산한다. 클라이언트가 보낸 단가/합계로 저장하지 않는다.
2. 고객은 자기 테이블의 현재 세션 주문만 만들고 읽는다 (`tableId`는 토큰에서만 얻음, 요청 본문으로 받지 않음).
3. 쓰기 작업은 모두 `BEGIN IMMEDIATE` 트랜잭션이며 실패 시 전체 롤백. 외부 부작용(이벤트)은 커밋 후.
4. 이벤트/로그에 비밀번호, 해시, 토큰을 남기지 않는다.
5. SQL은 모두 매개변수 바인딩을 쓴다 (`IN (?,...)`의 자리표시자 개수만 코드에서 생성).
