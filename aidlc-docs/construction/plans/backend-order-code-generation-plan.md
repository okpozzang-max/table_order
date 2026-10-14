# Code Generation Plan - backend-order (Unit 3)

이 문서는 Unit 3 `backend-order`의 Code Generation 단일 기준 문서입니다. 승인 후 Step 순서대로 생성하며, 각 Step 완료 즉시 체크박스를 `[x]`로 갱신합니다.

## Unit 컨텍스트

- **입력 설계**: `aidlc-docs/construction/backend-order/functional-design/` (domain-entities, business-logic-model, business-rules), 계약 `contracts/openapi.yaml`, backend-core 코드(`backend/app`)와 `aidlc-docs/construction/backend-core/code/code-summary.md`의 "backend-order에 넘기는 사항"
- **구현 스토리 (18개)**: US-C4.1, C4.2, C5.1, C5.2, A2.1, A2.2, A2.3, A2.4, A2.5, A3.1, A3.2, A3.3, A3.4, E1, E2, E5, E6, E8
- **의존성**: backend-core의 `Database`/`register_schema`, `MenuService.get_active_menus_by_ids`/`set_publisher`, `TokenService`, `require_admin`/`require_table`, `AppError` 체계, `ServerEvent`/`EventPublisher`/`safe_publish`, `Clock`/`utc_iso`. 기존 파일은 **제자리에서 수정**한다 (복사본 금지).
- **소유 산출물**: 스키마 모듈 `order` v1 (table_sessions, orders, order_items, order_history, order_history_items), TableService, OrderService, EventBroker, 라우터 3개, SSE 스트림
- **코드 위치**: 워크스페이스 루트 `C:\Users\okpoz\AWS\table_order\backend\` (문서는 `aidlc-docs/construction/backend-order/code/`에 요약만)
- **환경**: Python 3.14.4, 기존 `.venv` 재사용. 새 의존성은 `tzdata==2026.5`(PyPI 확인, Windows용 IANA 시간대 데이터) 하나. 개발 의존성 추가 없음 (SSE 통합 테스트는 기존 `httpx` + 스레드에서 띄운 `uvicorn` 사용)
- **자동화 규칙**: UI 코드 없음 -> `data-testid` 해당 없음

## 구현 방침 (설계에서 정한 사항의 코드 수준 결정)

| 항목 | 결정 |
|---|---|
| 서비스 | 동기 함수 (FastAPI가 스레드풀에서 실행). `Database.transaction()`(BEGIN IMMEDIATE)과 `Database.connection()`(읽기) 사용. 시각은 주입된 `clock` |
| 요청 검증 | core와 같은 방식: 타입만 Pydantic 모델, 값 규칙은 `validate_*` 함수가 필드별 문구를 모아 `ValidationFailed`로 던짐 (`schemas.py`에 추가). 경로/쿼리 변수 형식 오류는 기존 `RequestValidationError` 매핑 사용, 필요한 필드 문구는 `FIELD_MESSAGES`에 추가 |
| 파일 구성 | 설계대로 라우터 3개(`customer_orders.py`, `admin_orders.py`, `admin_tables.py`) 신규. 기존 `customer.py`/`admin.py`는 건드리지 않고 `main.py`에서 추가 등록 |
| EventBroker | 구독별로 자신의 이벤트 루프와 `asyncio.Queue`를 가진다. `publish()`는 스레드 어디서나 호출 가능하며 구독별로 `loop.call_soon_threadsafe`로 넘긴다 (설계의 `attach_loop` 대신 구독 시점에 루프를 잡아 lifespan 없이도 동작. 구독자가 없으면 아무 일도 하지 않음). `close_all()`은 lifespan 종료에서 호출 |
| SSE | 스트림 로직은 테스트 가능한 비동기 제너레이터(`stream_events`)로 분리하고 `StreamingResponse`로 감싼다. 토큰 `exp` 도달 시 종료, `finally`에서 구독 해제 |
| 토큰 만료 정보 | `AdminPrincipal`에 `expires_at`(epoch 초)을 선택 필드로 추가해 SSE가 사용 (기존 사용처 영향 없음) |
| 멱등/경쟁 | 설계 3절 순서 그대로: 선조회 -> 메뉴/가격 검증 -> `BEGIN IMMEDIATE` 재확인 -> UNIQUE 위반 시 기존 주문 반환 |
| 날짜 필터 | `zoneinfo.ZoneInfo(settings.timezone)`로 현지 자정 -> UTC 문자열 경계 계산 |
| 이벤트 발행 | 항상 커밋 후 `safe_publish` |

---

## 생성 단계

### Step 1. 설정과 의존성
- [x] `backend/requirements.txt`에 `tzdata==2026.5` 추가, `requirements.lock.txt` 갱신, 가상환경에 설치
- [x] `app/config.py`: `timezone`(기본 `Asia/Seoul`, 시작 시 `ZoneInfo` 로드 검증), `sse_keepalive_seconds`(기본 15, >=1), `sse_queue_size`(기본 100, >=1)
- [x] `backend/.env.example`: 선택 키 `TIMEZONE`, `SSE_KEEPALIVE_SECONDS`, `SSE_QUEUE_SIZE` 주석 추가
- [x] 단위 테스트(`tests/unit/test_errors_config.py` 확장): 기본값, 잘못된 시간대 이름 -> `ConfigError`(키 이름만), 0 이하 거부
- **스토리**: 기반 (US-A3.4 날짜 경계)

### Step 2. 도메인 예외 (`app/errors.py`)
- [x] `MenuUnavailable(menu_ids)`, `PriceChanged(current_prices)`, `InvalidTransition`, `NoActiveSession`, `DuplicateTable` (모두 409, `details`/문구는 domain-entities 6절)
- [x] `FIELD_MESSAGES`에 `items`, `clientOrderId`, `clientTotal`, `status`, `from`, `to`, `page`, `size`, `table`, `orderId`, `tableId` 문구 추가 (business-rules 2절)
- [x] 단위 테스트: 각 예외의 상태 코드/`code`/본문(`details`) 형식
- **스토리**: US-E2, E5, E8, A3.1

### Step 3. 요청/응답 모델과 검증 (`app/schemas.py`)
- [x] 모델(camelCase alias): `OrderCreateItem`, `OrderCreateRequest`, `OrderItemOut`, `OrderOut`, `OrderPageOut`, `StatusChangeRequest`, `TableSummaryOut`, `TableInfoOut`, `TableRegisterRequest`, `SessionSummaryOut`, `HistoryOrderOut`, `ServerEventOut`
- [x] `validate_order_create`(UUID 정규화, 항목 수 1~30, 수량 1~20, 중복 메뉴, `clientTotal` >= 0), `validate_table_register`, `validate_status`, `validate_history_range`, `validate_paging`
- [x] 단위 테스트: 경계값(수량 0/1/20/21, 항목 0/1/30/31, 중복 메뉴, UUID 형식/대문자 정규화, 번호 0/1/999/1000, 비밀번호 3/4/5자리·문자, 날짜 형식/역순, page/size 경계)
- **스토리**: US-C4.1, E1, E2, E5, A3.1, A3.4

### Step 4. 스키마 모듈 `order` (`app/schema_order.py`)
- [x] 5개 테이블 DDL + 인덱스 + CHECK/FK (domain-entities 1절), 모듈 `order` v1 등록 (`core` 다음)
- [x] 단위 테스트(`tests/unit/test_schema_order.py`): 생성 멱등, 활성 세션 부분 유니크(테이블당 1개, 종료 후 새 세션 허용), `(table_id, client_order_id)` 유니크, 상태 CHECK, 수량 CHECK, CASCADE 삭제, 외래키 위반, 스키마 버전 기록
- **스토리**: 기반 (전체)

### Step 5. EventBroker (`app/events.py`)
- [x] `EventBroker`: `subscribe()`(호출한 루프 기록), `unsubscribe`, `publish`(스레드 안전, 비블로킹), 큐 가득 참 -> `overflow` 종료, `close_all()`, 구독자 수 조회
- [x] `format_sse(event)`(`event:`/`data:` 한 줄 JSON, camelCase `tableId`), `stream_events(broker, ...)` 비동기 제너레이터: `: connected` -> 이벤트/`: keep-alive` -> 종료 조건(overflow, 서버 종료, `exp`, 연결 끊김) -> `finally` 해제
- [x] 단위 테스트(asyncio): 다른 스레드에서 발행해도 전달, 여러 구독자 팬아웃, 느린 구독자만 끊김, 해제 후 미전달, `close_all`, keep-alive 주기, 프레임 형식, 만료 시 종료, 구독자 없음 발행 무시, 발행 예외가 호출자에게 전파되지 않음
- **스토리**: US-A2.2, E6

### Step 6. TableService (`app/services/table_service.py`)
- [x] `register`(해시를 잠금 밖에서 계산, UNIQUE 위반 -> `DuplicateTable`), `list_tables`, `ensure_active_session(conn, table_id, now)`(내부용), `end_session`(이관 INSERT...SELECT 2개, 행 수 검증, 삭제, `ended_at`, 커밋 후 `session_ended`), `get_history`(현지 날짜 -> UTC 경계, 정렬, 항목 조립)
- [x] 단위 테스트(`tests/unit/test_table_service.py`, 주입 clock): 등록/중복/목록 `sessionActive`, 세션 생성 멱등, 이용 완료(주문 이관·ID/번호 보존·항목 순서 보존·합계 일치·`completedAt` 동일·상태 보존·0건 세션 종료), `NO_ACTIVE_SESSION`, 없는 테이블 404, 이관 중 실패 시 전체 롤백(고의 예외), 이용 완료 후 새 세션 ID, 과거 내역 정렬·날짜 경계(현지 자정 전후 1초, 시작만/종료만/둘 다)·다른 테이블 제외, 이벤트 발행 시점
- **스토리**: US-A3.1, A3.3, A3.4, E8

### Step 7. OrderService (`app/services/order_service.py`)
- [x] `create_order`(설계 3절 전체: 선조회, 이력 선조회, 메뉴/가격 검증, 트랜잭션 재확인, 세션 확보, 저장, 이벤트), `list_session_orders`, `dashboard`(배치 쿼리, 읽기 스냅샷), `get_order`, `change_status`(전이 표, 조건부 UPDATE), `delete_order`(요약 포함, 로그)
- [x] 단위 테스트(`tests/unit/test_order_service.py`): 서버 합계 재계산·스냅샷 저장(메뉴 가격 변경/삭제 후에도 기존 주문 불변), 첫 주문이 세션 생성/이후 재사용, 멱등(같은 키 -> 같은 주문·이벤트 1회·본문 달라도 기존 반환·다른 테이블은 별개·이력 이관 후 재전송), `MENU_UNAVAILABLE`(삭제/없는 ID 모두 나열, 저장 없음), `PRICE_CHANGED`(전체 메뉴 현재 가격, 순서), 두 오류 동시 해당 시 우선순위, 고객 내역 페이징/`hasNext`/세션 없음/다른 테이블 격리, 대시보드(모든 테이블·번호순·최신 3건·`table` 필터 전체·합계는 전체 기준·없는 번호 404·세션 없는 테이블 0), 상태 전이 표 전체 9칸, 404 우선, 삭제(요약 반영·마지막 주문 삭제 후 세션 유지·이력 주문 404), 동시 경쟁(스레드 두 개로 같은 키 주문 -> 1건, 같은 전이 -> 1건 성공)
- **스토리**: US-C4.1, C4.2, C5.1, C5.2, A2.1, A2.3, A2.4, A2.5, A3.2, E1, E2, E5, E8

### Step 8. 앱 조립 변경 (`app/deps.py`, `app/main.py`)
- [x] `AppContainer`에 `tables`, `orders`, `broker` 추가, `AdminPrincipal.expires_at` 추가
- [x] `build_container`: `schema_order` import(등록), `EventBroker` 생성, `event_publisher` 인자가 없으면 브로커를 발행기로 사용, `MenuService.set_publisher(publisher)`, 서비스 구성 (`event_publisher` 주입 시 테스트용으로 그것을 우선)
- [x] `create_app`: 신규 라우터 3개 등록(정적 서빙보다 앞), `lifespan` 종료 시 `broker.close_all()`
- [x] 단위/API 테스트에서 기존 `RecordingPublisher` 주입 방식이 그대로 동작하는지 확인
- **스토리**: US-A2.2, E6 (메뉴 변경 이벤트 연결)

### Step 9. 라우터와 SSE 엔드포인트
- [x] `app/routers/customer_orders.py`: `createOrder`(201/200 분기), `listSessionOrders`
- [x] `app/routers/admin_orders.py`: `getDashboard`, `getOrder`, `changeOrderStatus`, `deleteOrder`, `streamAdminEvents`(`StreamingResponse`, 헤더 `Cache-Control: no-cache`, `X-Accel-Buffering: no`)
- [x] `app/routers/admin_tables.py`: `listTables`, `registerTable`(201), `endSession`, `getTableHistory`
- [x] 계약의 operationId/태그/응답 코드/보안 스킴 사용, `responses`에 오류 모델과 `422` 포함
- **스토리**: 18개 전체

### Step 10. API 통합 테스트 (`tests/api/`)
- [x] `test_orders_api.py`: 주문 생성 201 / 재전송 200, 가격·메뉴 오류 본문, 검증 422 `fields`, 인증(관리자 토큰으로 고객 API 401 등), 고객 내역 페이징, 다른 테이블 격리, 이용 완료 후 비어 있음
- [x] `test_admin_orders_api.py`: 대시보드(필터·404·422), 상세, 상태 변경(409/404/422), 삭제 응답 `TableSummary`, 이벤트 발행 종류/payload/커밋 후(`RecordingPublisher`)
- [x] `test_tables_api.py`: 등록 201 / 중복 409 / 422, 등록 직후 해당 테이블로 `customerLogin` 성공, 목록, 이용 완료 200 / 409 / 404, 과거 내역 필터·422·404
- [x] `test_sse_api.py`: 실제 `uvicorn`을 스레드로 띄워 `httpx` 스트림으로 확인 - 인증 없으면 401, 헤더 3종, `: connected`, 주문 생성 후 **2초 이내** `order_created` 수신(프레임 형식), 메뉴 변경 시 `menu_changed`, keep-alive(짧은 주기 설정), 토큰 만료 시 스트림 종료, 연결 종료 후 구독자 수 0, 서버 종료 시 스트림 종료
- [x] 메뉴 삭제 후 주문 `MENU_UNAVAILABLE` 등 core-order 연동 확인
- **스토리**: 18개 전체

### Step 11. 계약 일치 테스트 확장 (`tests/contract/test_contract.py`)
- [x] 대상 operation에 backend-order 11개 추가 (경로/메서드, 성공 코드, 보안, 요청·응답 스키마 필드, 앱이 쓰는 오류 코드가 계약 부분집합)
- [x] 샘플 호출로 응답 본문이 계약 필수 필드를 포함하는지 확인 (`Order`, `OrderPage`, `TableSummary`, `TableInfo`, `SessionSummary`, `HistoryOrder`, SSE `ServerEvent`)
- [x] 불일치가 발견되면 `contracts/openapi.yaml` 수정 후 프론트엔드 `gen:api` + `tsc` 재확인
- **스토리**: 계약 준수 (전체)

### Step 12. 시드/통합 시나리오
- [x] `scripts/seed.py` 점검: `--reset`이 새 테이블을 FK 순서와 무관하게 비우는지 테스트 추가(`test_seed_scripts.py`), 코드 변경이 필요하면 최소 수정
- [x] `tests/integration/test_scenario.py`: 라이브 서버(uvicorn 스레드)에 `httpx`로 설계 13절 시나리오 1~9 수행 (관리자 SSE 구독 + 테이블 등록 -> 주문 -> 2초 내 수신 -> 상태 변경 -> 재전송 200 -> 가격 변경 `PRICE_CHANGED` -> 삭제 -> 이용 완료 -> 과거 내역 -> 새 세션)
- **스토리**: 통합 (전체)

### Step 13. 전체 검증과 스모크
- [x] `pytest` 전체 실행 (기존 197개 + 신규), 실패 0
- [x] 프론트엔드 `npm run build`(real 모드) 후 실제 서버 기동(`uvicorn --factory`, 임시 DB/임시 환경 값) -> 시드 -> 정적 `index.html` + SPA 폴백 + 위 시나리오 핵심 호출(curl 수준) 확인 -> 종료, 임시 파일 정리
- [x] 프론트엔드 `gen:api` + `tsc --noEmit` + `vitest` 재실행 (계약 변경 영향 확인)
- [x] 결과를 코드 요약에 기록. 브라우저에서 화면을 직접 조작하는 검증은 하지 않는다 (Build and Test 단계의 수동 확인 안내로 넘김)

### Step 14. 문서화
- [x] `backend/README.md`: 새 설정 키, 엔드포인트 요약, SSE 사용법, 테스트 실행(통합/SSE 포함), 전체 구동 방법(프론트엔드 빌드 -> 서버)
- [x] `aidlc-docs/construction/backend-order/code/code-summary.md`: 생성 산출물 표, 설계 대비 차이, 검증 결과, 확인하지 못한 것

### Step 15. 스토리 추적성 확인
- [x] 18개 스토리의 구현/테스트 위치를 요약 문서 표에 기록하고 아래 체크리스트 갱신

---

## 스토리 구현 체크리스트 (Step 완료 시 `[x]`)

[x] US-C4.1 [x] US-C4.2 [x] US-C5.1 [x] US-C5.2 [x] US-A2.1 [x] US-A2.2 [x] US-A2.3 [x] US-A2.4 [x] US-A2.5 [x] US-A3.1 [x] US-A3.2 [x] US-A3.3 [x] US-A3.4 [x] US-E1 [x] US-E2 [x] US-E5 [x] US-E6 [x] US-E8

## 범위 외 (이 Unit에서 하지 않는 것)
- 테이블 수정/삭제 API, 주문 항목 수정, 이력 페이지네이션, SSE 이벤트 재전송(Last-Event-ID)
- Docker/배포 산출물 (Infrastructure Design 생략)
- 브라우저 E2E 자동화 (frontend Plan Q6: A에 따라 제외). 브라우저 수동 확인 절차는 Build and Test 단계 문서로 제공
- 다중 프로세스/부하 시험 (단일 프로세스 소규모 전제)

## 규모 예상
- 15단계, 신규 소스 약 8개(`schema_order`, `events`, `table_service`, `order_service`, 라우터 3개 + 스키마 확장), 신규 테스트 파일 약 11개, 수정 파일 약 8개(`config`, `errors`, `schemas`, `deps`, `main`, `requirements*`, `.env.example`, `test_contract`, README)

## 설계 대비 차이 (미리 알림)
| 항목 | 설계 | 계획 | 이유 |
|---|---|---|---|
| EventBroker 루프 연결 | `attach_loop` (lifespan에서) | 구독 시점에 호출 루프 기록 | lifespan 없이도 동작하고 테스트 단순. 구독자가 없으면 발행은 무동작이라 결과 동일 |
