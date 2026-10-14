# Code Summary - backend-order (Unit 3)

애플리케이션 코드는 워크스페이스 루트의 `backend/`에 있습니다 (backend-core와 같은 앱에 추가). 이 문서는 요약만 담습니다.

## 생성/수정 산출물

| 영역 | 경로 | 내용 |
|---|---|---|
| 스키마 | `app/schema_order.py` (신규) | 모듈 `order` v1: `table_sessions`(활성 세션 부분 유니크), `orders`(`(table_id, client_order_id)` 유니크), `order_items`(메뉴 FK 없음, 스냅샷), `order_history`, `order_history_items` |
| 이벤트 | `app/events.py` (신규) | `EventBroker`(구독별 루프/큐, 스레드 안전 발행, overflow 시 해당 구독만 종료, `close_all`), `format_sse`, `stream_events`(connected/keep-alive/토큰 만료/해제), `CompositePublisher` |
| 서비스 | `app/services/table_service.py`, `order_service.py` (신규) | 테이블 등록/목록, 세션 확보, 이용 완료(이력 이관 단일 트랜잭션, 건수 검증), 과거 내역(현지 날짜 경계) / 멱등 주문 생성, 세션 주문 내역, 대시보드, 상태 전이, 삭제 |
| 조회 도구 | `app/services/order_queries.py`, `order_models.py` (신규) | 항목 일괄 조회(IN), 대시보드 요약(윈도 함수), 읽기 스냅샷, 값 객체, 주문 번호 계산 |
| 라우터 | `app/routers/customer_orders.py`, `admin_orders.py`(SSE 포함), `admin_tables.py` (신규) | 11개 operation |
| 수정 | `app/errors.py` | `MenuUnavailable`, `PriceChanged`, `InvalidTransition`, `NoActiveSession`, `DuplicateTable`, 필드 문구 추가 |
| | `app/schemas.py` | 주문/테이블 요청·응답 모델, `validate_order_create/status/table_register/history_range` |
| | `app/config.py`, `.env.example` | `TIMEZONE`(시작 시 검증), `SSE_KEEPALIVE_SECONDS`, `SSE_QUEUE_SIZE` |
| | `app/deps.py`, `app/main.py` | 컨테이너에 `tables`, `orders`, `broker` 추가, `AdminPrincipal.expires_at`, 이벤트 발행기 연결(`menu_changed` 포함), lifespan 종료 시 `close_all()`, 라우터 등록 |
| | `requirements.txt`, `requirements.lock.txt` | `tzdata==2026.5` |
| 테스트 | `tests/unit`(스키마, 이벤트, 테이블/주문 서비스, 검증), `tests/api`(주문, 관리자 주문, 테이블, SSE), `tests/contract`(확장), `tests/integration/test_scenario.py`, `tests/live.py`(실제 서버 도구), `tests/order_helpers.py` | 아래 검증 결과 참고 |
| 문서 | `backend/README.md` | 설정 키, API 요약, SSE 사용법, 전체 구동, 테스트 실행, 제한 |

## 계약 변경

Functional Design 단계에서 `contracts/openapi.yaml`에 `422`(경로·쿼리 값 형식 오류)를 `listSessionOrders`, `getDashboard`, `getOrder`, `deleteOrder`, `endSession`에 추가했습니다. 코드 생성 중 추가 변경은 없었고, 계약 일치 테스트가 19개 operation 모두 통과합니다. 프론트엔드 `gen:api` 재실행 후 변경 없음, `tsc --noEmit`과 vitest 166개 통과.

## 설계/계획 대비 차이

| 항목 | 설계/계획 | 실제 | 이유 |
|---|---|---|---|
| EventBroker 루프 연결 | `attach_loop` (lifespan) | 구독 시점에 호출 루프를 기록, 발행은 구독별 `call_soon_threadsafe` | lifespan 없이도 동작, 테스트 단순. 계획서에서 미리 알린 차이 |
| 발행기 구성 | 브로커 또는 주입 발행기 | 브로커는 항상 연결, `event_publisher`는 `CompositePublisher`로 추가 전달 | 기존 `RecordingPublisher` 기반 테스트를 유지하면서 같은 앱에서 SSE도 검증 |
| 쿼리/경로 검증 | `validate_*` | `page`/`size`/`table`/`from`/`to`/경로 ID는 FastAPI 제약(`Query(ge, le)`, `date`)과 `RequestValidationError` 매핑, 날짜 순서만 `validate_history_range` | OpenAPI 파라미터가 계약과 자동으로 일치 (파라미터 비교 테스트로 확인) |
| 테이블 비밀번호 | `^\d{4}$` | 등록은 ASCII 숫자 `[0-9]{4}`만 | 파이썬 `\d`가 전각 숫자를 허용해, 로그인할 수 없는 비밀번호가 저장될 수 있음. 로그인 검증(core)은 기존 규칙 유지 (전각 입력은 어차피 해시 불일치로 401) |
| 멱등 재응답 내용 | "기존 주문을 반환" | 재응답은 **현재 상태**의 주문 (예: 이미 `COMPLETED`면 그 상태) | 고객 재시도 시 최신 정보를 보여주는 것이 맞음 |
| 서버 종료 | `close_all()` 호출 | 호출은 하지만, uvicorn은 열린 연결이 닫힌 뒤 lifespan 종료를 실행하므로 열린 SSE가 있으면 `--timeout-graceful-shutdown`이 필요 | 실제 동작 확인 후 README 실행 명령에 옵션 반영, 테스트(`test_server_shutdown_with_open_stream_does_not_hang`)로 확인 |
| 시드 스크립트 | 점검 | 코드 변경 없음 (`--reset`이 모든 앱 테이블을 FK 무시로 비움). 주문 테이블 초기화/ID 리셋은 테스트로 추가 | |

## 검증 결과

| 항목 | 결과 |
|---|---|
| 백엔드 `pytest` 전체 | 522개 통과 (기존 197개 + 신규 325개), 2회 연속 실행 모두 통과 |
| 신규 테스트 영역 | 스키마 제약, EventBroker/SSE 프레임·keep-alive·만료·overflow·해제, 테이블/주문 서비스(경계값, 동시성 경쟁 2건), API(주문·대시보드·상태·삭제·테이블·이력), 실제 서버 SSE 12건, 계약 일치(19 operation x 7항목 + 실제 응답 필수 필드 + 오류 본문), 통합 시나리오 1건 |
| SSE 2초 요구 | 실제 uvicorn 스레드 테스트에서 주문 응답 직후 `order_created` 수신 < 2초, 실제 프로세스 스모크에서 0.046초 |
| 실제 프로세스 스모크 | `uvicorn --factory`(임시 DB, 임시 환경값), 프론트엔드 `dist`(real 모드 빌드): 시드 2회(멱등), `/` 및 SPA 경로 200, 로그인, SSE 연결, 주문 201/재전송 200, 이벤트 3종 순서(`order_created`, `order_status_changed`, `session_ended`), 건너뛰기 전이 409, `PRICE_CHANGED` 409, 토큰 없음 401, 테이블 등록 201/중복 409, 이용 완료 200과 과거 내역, 이용 완료 후 고객 내역 비움. 서버 stderr에 오류 없음. 임시 파일 정리 완료 |
| 프론트엔드 영향 | `gen:api` 후 변경 없음, `tsc --noEmit` 통과, vitest 25개 파일 166개 통과, `npm run build` 성공 |

## 확인하지 못한 것

- 브라우저에서 프론트엔드 화면을 직접 조작하는 통합 확인 (자동화는 범위 외로 결정, HTTP/SSE 수준에서 프론트엔드 real 모드와 같은 요청으로 검증). Build and Test 단계의 수동 확인 절차로 넘김
- Windows 콘솔의 실제 Ctrl+C 종료 동작 (스모크는 프로세스를 강제 종료, 종료 동작은 서버 스레드 + `timeout_graceful_shutdown` 테스트로 확인)
- 다중 프로세스/다중 워커 (EventBroker가 프로세스 메모리에 있어 단일 프로세스 전제), 동시 접속 부하
- 리버스 프록시 뒤의 SSE 버퍼링 (`X-Accel-Buffering: no` 헤더만 설정)
- 경고: Starlette `TestClient`가 `httpx` 사용 중단 예고(`httpx2` 권장) 경고를 출력한다 (backend-core부터 동일, 동작 영향 없음)

## 스토리 구현 위치 (18개)

| 스토리 | 구현 | 주요 테스트 |
|---|---|---|
| US-C4.1 | `OrderService.create_order`, `POST /api/customer/orders` | `test_order_service.TestCreate`, `test_orders_api.TestCreateOrder` |
| US-C4.2 | 응답 `orderNumber`(ID 4자리), 201/200 | `test_orders_api.test_created_201_with_contract_shape`, `test_scenario` |
| US-C5.1 | `OrderService.list_session_orders`, `GET /api/customer/orders` | `TestListSessionOrders`, `test_orders_api.TestListOrders` |
| US-C5.2 | 상태 변경이 같은 목록에 반영(폴링 대상) | `test_status_updates_are_visible_to_polling_customer` |
| US-A2.1 | `OrderService.dashboard`, `GET /api/admin/dashboard` | `TestDashboard` (서비스/API) |
| US-A2.2 | `EventBroker`, `GET /api/admin/events`, `order_created` | `test_events.py`, `test_sse_api.py`, `test_scenario` |
| US-A2.3 | `OrderService.get_order`, `GET /api/admin/orders/{id}` | `TestGetOrder`, `TestOrderDetail` |
| US-A2.4 | `OrderService.change_status`, `PATCH .../status` | `TestChangeStatus`(전이 9칸 + 경쟁), API `TestChangeStatus` |
| US-A2.5 | 대시보드 `table` 파라미터 | `test_table_filter_*` |
| US-A3.1 | `TableService.register/list_tables`, `POST/GET /api/admin/tables` | `test_table_service.TestRegisterAndList`, `test_tables_api.TestRegisterAndList` |
| US-A3.2 | `OrderService.delete_order`, `DELETE /api/admin/orders/{id}` | `TestDelete`, `TestDeleteOrder` |
| US-A3.3 | `TableService.end_session`, `POST .../end-session` | `TestEndSession`, `test_tables_api.TestEndSession` |
| US-A3.4 | `TableService.get_history`, `GET .../history` | `TestHistory`(KST 자정 경계), `test_tables_api.TestHistory` |
| US-E1 | 실패 시 부분 저장 없음 + `clientOrderId` 멱등 재전송 | `test_unavailable_menus_listed_and_nothing_saved`, `test_replay_*` |
| US-E2 | `MenuUnavailable` (`details.menuIds`) | `test_unavailable_menu_409_lists_ids` |
| US-E5 | `InvalidTransition` | `test_invalid_transitions_409`, 전이 표 테스트 |
| US-E6 | keep-alive, overflow/만료/종료 시 스트림 종료, 해제 | `test_keep_alive_comments`, `test_stream_ends_when_token_expires`, `test_disconnect_releases_subscription` |
| US-E8 | 삭제/이용 완료 단일 트랜잭션, `NO_ACTIVE_SESSION` | `test_failure_during_archive_rolls_everything_back`, `test_second_call_409_*` |

## Build and Test 단계로 넘기는 사항

1. 브라우저 수동 확인 절차: 프론트엔드 빌드(real) -> 서버 -> 고객 태블릿 주문 -> 관리자 대시보드 실시간 강조 -> 상태 변경 -> 이용 완료 -> 과거 내역 (README의 "전체 구동" 참고).
2. 전체 명령 요약: 백엔드 `pytest`(522), 프론트엔드 `npm run gen:api; npx tsc --noEmit; npx vitest run; npm run build`.
3. 단일 프로세스 전제와 `--timeout-graceful-shutdown` 권장 사항을 운영 안내에 포함.
