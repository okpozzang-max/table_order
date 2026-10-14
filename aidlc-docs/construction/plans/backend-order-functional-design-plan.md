# Functional Design 계획 - backend-order (Unit 3)

대상 Unit: `backend-order` (테이블 세션, 주문, 실시간). 구성: TableService, OrderService, EventBroker, SSE 스트림, 라우터(`customer_orders`, `admin_orders`, `admin_tables`), 스키마 확장(`order` 모듈), 통합(실제 API 연결).
참고: `unit-of-work.md`, `unit-of-work-story-map.md`(담당 스토리 18개: US-C4.1, C4.2, C5.1, C5.2, A2.1~A2.5, A3.1~A3.4, E1, E2, E5, E6, E8), `contracts/openapi.yaml`(11개 operation: createOrder, listSessionOrders, getDashboard, getOrder, changeOrderStatus, deleteOrder, streamAdminEvents, listTables, registerTable, endSession, getTableHistory), `backend-core/code/code-summary.md`(연동 지점), 프론트엔드 `domain-entities.md`/`business-rules.md`(계약 요구)

이 단계에서는 주문/세션/이력 스키마, 상태 전이, 멱등성, 트랜잭션 경계, 이력 이관, SSE 이벤트 규격을 상세 설계합니다.

아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요. "추천해서 진행"이라고 적으셔도 됩니다.

---

## Part A. 질문

## Question 1
테이블 이용 완료 시 주문을 "과거 이력으로 이동"하는 방식은 어떻게 할까요? (요구사항: OrderHistory 테이블에 저장, 세션 ID로 그룹화, 완료 시각 기록)

A) 별도 이력 테이블(`order_history`, `order_history_items`)로 복사한 뒤 현재 주문 테이블에서 삭제한다 (요구사항 문구에 가장 가까움)

B) 같은 `orders` 테이블에 두고 세션 종료 시각만 기록해 "과거"로 취급한다 (복사 없음, 단순하고 안전)

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - 요구사항/서비스 설계의 "OrderHistory로 이관"과 일치. 주문 ID는 그대로 유지(AUTOINCREMENT라 재사용 없음). 복사+삭제는 한 트랜잭션.

## Question 2
주문 번호 형식은 어떻게 할까요? (고객 화면 완료 메시지와 관리자 화면에 표시됩니다. 프론트엔드 가짜 API는 4자리 순번을 사용 중)

A) 전체 순번 4자리 (`0001`, `0002` ...). 9999를 넘으면 자릿수가 늘어남

B) 영업일(날짜) + 일별 순번 (`20261014-001`). 날짜가 바뀌면 순번 초기화

C) 테이블 번호 + 순번 (`T3-007`). 테이블마다 순번 진행

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - 주문 ID를 4자리로 채운 값(`0001`). 추가 상태/시간대 의존이 없고 유일성이 보장되며 프론트엔드 가짜 API와 동일.

## Question 3
관리자의 주문 삭제(직권 수정)는 어떻게 처리할까요?

A) 물리 삭제 (행을 실제로 지움, "주문 즉시 삭제" 문구에 부합)

B) 소프트 삭제 (삭제 표시만 하고 모든 조회에서 제외, 감사/복구 용도로 보관)

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - 물리 삭제. 요구사항의 "즉시 삭제"와 이력 이관(Q1)과 일관. 추적은 서버 로그(주문/테이블/금액)로 남김.

## Question 4
과거 주문 내역의 날짜 필터(시작일~종료일)는 어떤 날짜를 기준으로 할까요?

A) 주문 생성일

B) 이용 완료일 (테이블 이용이 끝난 날)

X) Other (please describe after [Answer]: tag below)

[Answer]: B (추천 위임) - 이용 완료일. 계약의 `completedAt`이 정렬/표시 기준이므로 필터도 같은 기준.

## Question 5
날짜 필터의 "하루" 경계는 어느 시간대 기준으로 할까요? (DB에는 UTC로 저장, 한국 매장 기준)

A) `Asia/Seoul` 고정 (설정 `TIMEZONE`으로 변경 가능, IANA 시간대 데이터가 없는 Windows를 위해 `tzdata` 패키지 추가)

B) 서버 OS의 로컬 시간대 사용 (추가 패키지 없음, 서버 설정에 의존)

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - `Asia/Seoul` 고정(설정 `TIMEZONE`), `tzdata` 추가.

## Question 6
한 주문 안에 같은 메뉴가 두 번 이상 들어오면 어떻게 할까요? (프론트엔드는 메뉴별 한 줄로 보내므로 정상 사용에서는 발생하지 않음)

A) 입력 검증 오류(422)로 거부

B) 수량을 합산해서 한 줄로 처리

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - 422, `fields.items`. 프론트엔드는 중복 줄을 만들지 않으므로 합산은 불필요하고 수량 20 한도를 우회할 수 있음.

## Question 7
주문 한도는 어떻게 할까요? (수량은 메뉴당 1~20으로 이미 확정)

A) 한 주문에 서로 다른 메뉴 최대 30종류, 총 금액 제한 없음

B) 종류 제한 없음 (수량 제한만)

X) Other (please describe after [Answer]: tag below)

[Answer]: A (추천 위임) - 서로 다른 메뉴 최대 30종류, 총 금액 제한 없음(수량 20 x 가격 100만원 x 30종 = 6억으로 정수 범위 안).

---

## Part B. 별도 질문 없이 적용할 설계 가정 (이견이 있으면 알려주세요)

| # | 가정 |
|---|---|
| G1 | 스키마 모듈 `order` v1을 `register_schema`로 등록한다: `table_sessions`, `orders`, `order_items` (+ Q1 답변에 따라 이력 테이블). 주문 항목은 주문 시점의 `menu_name`, `unit_price`를 복사해 저장하고 `menus`에 외래키를 두지 않는다 (메뉴 소프트 삭제/가격 변경과 독립). |
| G2 | 테이블 세션: 테이블당 활성 세션(`ended_at IS NULL`)은 최대 1개 (부분 유니크 인덱스). 첫 주문 시 같은 트랜잭션에서 생성, 이용 완료 시 `ended_at` 기록. 세션 ID는 `sess_` + 무작위 12자리 16진수. |
| G3 | 주문 생성은 `BEGIN IMMEDIATE` 한 트랜잭션: 메뉴 검증 -> 합계 재계산 -> 세션 확보 -> 주문/항목 저장. 커밋 후 `order_created` 발행. |
| G4 | 멱등성: `(table_id, client_order_id)` 유니크. 같은 `clientOrderId`가 이미 있으면 새로 만들지 않고 기존 주문을 **200**으로 반환(최초 생성은 201). 이벤트는 최초 생성 때만 발행. |
| G5 | 검증 순서: 요청 형식(422) -> 삭제/없는 메뉴(409 `MENU_UNAVAILABLE`, `details.menuIds`) -> 합계 불일치(409 `PRICE_CHANGED`, `details.currentPrices`에 주문 메뉴 전체의 현재 가격). 합계는 서버 현재 가격으로 재계산하며 클라이언트 금액은 비교에만 쓴다. |
| G6 | 상태 전이는 `PENDING -> PREPARING -> COMPLETED`만. 조건부 `UPDATE ... WHERE id=? AND status=<기대 상태>`로 경합을 막고, 불일치하면 409 `INVALID_TRANSITION`. 존재하지 않는/종료된 세션의 주문은 404. |
| G7 | 고객 주문 내역: 현재 활성 세션의 주문만, 최신순(id 내림차순). `page`는 0부터, `size` 기본 10(1~50), 응답은 계약의 `OrderPage`. 활성 세션이 없으면 빈 목록. |
| G8 | 대시보드: 등록된 모든 테이블을 번호 오름차순으로 반환(주문 없는 테이블 포함). `table` 파라미터가 없으면 각 테이블의 활성 세션 주문 중 최신 3건, 있으면 해당 테이블의 활성 세션 전체 주문(최신순). 없는 테이블 번호는 404. `totalAmount`, `orderCount`는 항상 활성 세션 전체 기준. |
| G9 | 주문 삭제는 활성 세션의 주문만 가능 (이력으로 넘어간 주문은 404). 삭제 후 해당 테이블의 갱신된 `TableSummary`(기본 최신 3건)를 반환. 마지막 주문을 삭제해도 세션은 유지된다(세션 종료는 이용 완료로만). |
| G10 | 이용 완료: 활성 세션이 없으면 409 `NO_ACTIVE_SESSION`. 활성 세션이면 (주문이 0건이어도) 한 트랜잭션에서 주문을 이력으로 처리하고 세션을 종료한다. 이력의 `completedAt`은 세션 종료 시각(해당 세션 모든 주문 동일). 응답 `SessionSummary`는 이관 주문 수와 합계. |
| G11 | 과거 내역: 시간 역순(`completedAt` 내림차순, 같으면 주문 ID 내림차순). 필터는 시작일/종료일 포함 구간, 둘 다 선택 사항, 시작일 > 종료일이면 422. 없는 테이블은 404. |
| G12 | 테이블 등록: 번호 1~999, 비밀번호 숫자 4자리(bcrypt 해시 저장), 중복이면 409 `DUPLICATE_TABLE`, 응답 201 `TableInfo(sessionActive=false)`. 등록 즉시 태블릿 로그인 가능(`tables`는 core 소유). 테이블 수정/삭제 API는 없다. |
| G13 | `listTables`/`TableInfo.sessionActive`는 활성 세션 존재 여부로 계산한다. |
| G14 | SSE `GET /api/admin/events`: 관리자 토큰 필요, `Content-Type: text/event-stream`, 헤더 `Cache-Control: no-cache`, `X-Accel-Buffering: no`. 형식 `event: <type>\ndata: <ServerEvent JSON 한 줄>\n\n`. 연결 유지를 위해 15초마다 `: keep-alive` 주석 전송. |
| G15 | EventBroker: 구독자별 크기 100의 큐. 스레드풀의 서비스에서 `publish()`는 이벤트 루프로 안전하게 전달(`call_soon_threadsafe`)하며 절대 블로킹하지 않는다. 큐가 가득 찬 느린 구독자는 연결을 끊어 클라이언트가 재연결 후 재조회하게 한다. 연결 종료 시 구독 해제. 서버 종료 시 모든 스트림을 닫는다. |
| G16 | 이벤트 종류와 `payload`: `order_created {orderId}`, `order_status_changed {orderId, status}`, `order_deleted {orderId}`, `session_ended {archivedOrderCount}`, `menu_changed {}`. `tableId`는 해당 테이블(메뉴 변경은 null). 모두 커밋 후 발행. |
| G17 | 새 도메인 오류: `MenuUnavailable`, `PriceChanged`, `InvalidTransition`, `NoActiveSession`, `DuplicateTable` (모두 409, 계약의 코드와 `details`). 기존 `NotFound`, `ValidationFailed`를 재사용. |
| G18 | 응답의 시각은 UTC ISO 8601. 주문 번호는 서버가 생성하며 Q2 형식을 따른다. |
| G19 | 통합 단계: 같은 FastAPI 앱이 `frontend/dist`를 서빙하므로 프론트엔드 real 모드와 같은 오리진으로 동작한다. 최종 검증에 프론트엔드 `VITE_API_MODE=real` 빌드로 통합 시나리오(주문 -> SSE -> 상태 변경 -> 이용 완료)를 포함한다. |

---

## Part C. 실행 체크리스트 (답변 확정 후 수행)

### 분석
- [x] A1. unit-of-work.md, 스토리 맵(18개 스토리), 계약의 주문/테이블/SSE 경로, backend-core 연동 지점 재확인
- [x] A2. 답변 분석 및 모호성 해소 (필요 시 후속 질문)

### 산출물 생성 (`aidlc-docs/construction/backend-order/functional-design/`)
- [x] D1. `domain-entities.md`: 테이블 정의(table_sessions, orders, order_items, 이력), 제약/인덱스, 상태 enum, 이벤트 모델, 도메인 예외
- [x] D2. `business-logic-model.md`: 주문 생성, 조회, 대시보드, 상태 변경, 삭제, 이용 완료, 과거 내역, 테이블 등록, SSE 구독/발행 흐름, 트랜잭션 경계, 통합 시나리오
- [x] D3. `business-rules.md`: 검증, 멱등성, 가격 재계산, 전이 표, 세션 규칙, 한도, 오류 매핑, SSE/이벤트 규격
- [x] D4. 계약(`contracts/openapi.yaml`)의 backend-order 11개 operation과 설계 일치 검증 (누락/불일치는 계약 수정)
- [x] D5. 담당 스토리 18개 반영 여부 검증

### 마무리
- [x] F1. `aidlc-state.md`, `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기


---

## 결과 메모

- Q1~Q7은 모두 위임되어 AI 추천(A, A, A, B, A, A, A)으로 확정했고, Part B 가정 G1~G19에는 이견이 없어 그대로 적용했습니다. 추가 가정 G20~G22는 `business-rules.md`에 있습니다.
- D4: `contracts/openapi.yaml`에 경로/쿼리 변수 형식 오류용 `422`를 `listSessionOrders`, `getDashboard`, `getOrder`, `deleteOrder`, `endSession`에 추가했습니다 (backend-core의 `deleteMenu` 선례). 프론트엔드 타입 재생성 후 `tsc --noEmit` 통과, vitest 166개 통과, 백엔드 pytest 197개 통과(계약 변경 영향 없음).
- D5: 담당 스토리 18개 모두 `business-logic-model.md` 15절에 반영.
