# Code Summary - backend-core (Unit 2)

애플리케이션 코드는 워크스페이스 루트의 `backend/`에 있습니다. 이 문서는 요약만 담습니다.

## 생성 산출물

| 영역 | 경로 | 내용 |
|---|---|---|
| 의존성/설정 | `backend/requirements.txt`, `requirements-dev.txt`, `requirements.lock.txt`, `pytest.ini`, `.env.example`, `.gitignore` | 직접 의존성 `==` 고정 + 전이 의존성 포함 lock |
| 설정 | `app/config.py` | `.env` 로드/검증, 키 이름만 노출하는 `ConfigError` |
| DB | `app/db.py`, `app/schema_core.py` | WAL/외래키/busy_timeout 연결, `BEGIN IMMEDIATE` 트랜잭션, 모듈별 스키마 레지스트리(`schema_version`), core 스키마 |
| 보안 | `app/security.py` | bcrypt(72바이트 처리), JWT HS256(주입 clock으로 만료 판정), role/storeId 검증 |
| 오류 | `app/errors.py` | 도메인 예외, `ApiErrorBody` 생성, 요청 검증 오류 -> 필드별 문구 |
| 모델/검증 | `app/schemas.py` | camelCase 요청/응답 모델, `validate_*` (프론트엔드와 같은 규칙/문구) |
| 서비스 | `app/services/auth_service.py`, `menu_service.py` | 로그인/잠금, 메뉴 조회/CRUD/소프트 삭제/순서 |
| 의존성 | `app/deps.py` | 컨테이너, `require_admin`, `require_table` |
| 라우터 | `app/routers/customer.py`, `admin.py` | 8개 operation |
| 앱 | `app/main.py` | `create_app`, 오류 핸들러, 정적 서빙 + SPA 폴백 |
| 이벤트 포트 | `app/events_port.py` | `EventPublisher`, `NullPublisher`, `safe_publish` |
| 스크립트 | `scripts/seed.py`, `scripts/hash_password.py` | 멱등 시드(`--reset`), 해시 생성 |
| 테스트 | `tests/unit`(6개 파일), `tests/api`(3), `tests/contract`(1), `tests/conftest.py` | 아래 참고 |
| 문서 | `backend/README.md` | 설치/설정/실행/테스트/연동 지점 |

## 계약 변경 (이 Unit에서 `contracts/openapi.yaml`에 반영)

| 변경 | 이유 |
|---|---|
| `customerLogin`에 `429 ACCOUNT_LOCKED` 추가 | 테이블 로그인 실패 제한(Functional Design Q3) |
| `deleteMenu`에 `422 VALIDATION_ERROR` 추가 | 경로 변수(`menuId`)가 정수가 아닐 때 구현이 422를 반환. 계약 일치 테스트가 발견 |

변경 후 프론트엔드 타입을 재생성했고 프론트엔드 타입 검사는 깨끗하다 (프론트엔드 코드 변경 없음).

## 설계 대비 차이

| 항목 | 설계 | 실제 | 이유 |
|---|---|---|---|
| 라우터 파일 | `customer_auth`, `customer_menu`, `admin_auth`, `admin_menus` 4개 | `routers/customer.py`, `routers/admin.py` 2개 | 같은 접두사를 공유하고 규모가 작아 합침 (경로/동작 동일) |
| 요청 검증 | Pydantic 제약 + 매핑 표 | 타입만 Pydantic, 값 규칙은 `validate_*` | 같은 필드명(`storeId`, `password`)이 폼마다 다른 문구를 가져 모델별 문구가 필요 |
| 허용되지 않는 메서드 | 405 | 404 `NOT_FOUND` | 정적 서빙 폴백이 모든 메서드를 받음 (business-rules 4절 갱신) |
| 로그인 잠금 확인 | 한 트랜잭션 | 잠금 확인(짧은 트랜잭션) -> 해시 검증(잠금 밖) -> 결과 반영(짧은 트랜잭션, 잠금 재확인) | bcrypt(수백 ms) 동안 DB 쓰기 잠금을 잡지 않기 위해. 동시 시도가 잠금을 우회하지 않도록 반영 직전에 다시 확인 |
| 경로 변수 이름 | - | `/menus/{menuId}` | 계약과 동일해야 일치 테스트가 통과 |

## 검증 결과

| 항목 | 결과 |
|---|---|
| `pytest` 전체 | 197개 통과 (단위 107, API 통합 38, 계약 일치 52) |
| 실제 서버 스모크 (`uvicorn --factory`, 임시 DB) | 시드 2회(멱등 확인) -> 관리자/테이블 로그인 200 -> 메뉴 조회 12개(4 카테고리) -> 정적 `index.html`/SPA 폴백/에셋 200 -> 토큰 없음 401 -> 없는 API 404 JSON -> 5번째 실패 429(900초), 잠금 중 올바른 비밀번호 429 -> 서버 stderr 없음 |
| 프론트엔드 영향 | 계약 변경 후 `gen:api`, `tsc --noEmit` 통과 |

테스트가 다루는 핵심: 5회/15분 잠금(만료 후 재집계, 사용자명 변경 회피 불가, 재시작 후 유지), 테이블 10회/5분 잠금(테이블별 독립, 없는 테이블·다른 매장은 집계 안 함), 토큰 만료(16시간 경계)·role 교차·변조·`alg=none`·삭제된 테이블 토큰, 메뉴 순서 규칙(새 카테고리/이동/삭제 시 재번호, 안정적 카테고리 순서), 소프트 삭제(조회 제외, 이름 재사용, ID 비재사용), 이벤트 발행 시점(커밋 후, 실패 시 미발행, 발행기 오류 무시), 경로 이탈 방지, 내부 정보 비노출(500), 계약 일치(경로/상태 코드/보안/스키마 모양/오류 본문).

확인하지 못한 것:
- 브라우저에서 이 백엔드와 프론트엔드를 실제로 연결한 화면 동작 (프론트엔드의 real 모드 연동은 backend-order 완료 후 통합 단계에서 확인)
- 다중 프로세스/동시 부하에서의 SQLite 경합 (단일 프로세스 소규모 전제)
- 경고: Starlette `TestClient`가 `httpx` 사용 중단 예고(`httpx2` 권장) 경고를 출력한다. 현재 동작에는 영향이 없다.

## 스토리 구현 위치 (13개)

| 스토리 | 구현 | 주요 테스트 |
|---|---|---|
| US-C1.1 | `AuthService.login_table`, `routers/customer.py` | `test_auth_service.TestTableLogin`, `test_auth_api.TestTableLoginApi` |
| US-C2.1, C2.2 | `MenuService.list_grouped`, `GET /api/customer/menus` | `test_menus_api.TestListing`, `test_menu_service.TestOrdering` |
| US-A1.1 | `AuthService.login_admin`, `routers/admin.py` | `TestAdminLogin`, `TestAdminLoginApi` |
| US-A1.2 | `TokenService`(16시간), `deps.require_*` | `test_security_schemas.TestTokens`, `TestTokenEnforcement.test_token_expires_after_16_hours` |
| US-A4.1 | `GET /api/admin/menus` | `TestListing` |
| US-A4.2 | `MenuService.create`, `POST /api/admin/menus` | `TestCreate` |
| US-A4.3 | `MenuService.update/delete` | `TestUpdateDelete`, `TestSoftDeleteAndNames` |
| US-A4.4 | `MenuService.reorder`, `PUT /api/admin/menus/reorder` | `TestReorder`, `TestOrdering` |
| US-E3 | `InvalidCredentials`/`AccountLocked`(테이블) | `TestTableLoginApi.test_invalid_credentials` |
| US-E4 | 관리자 잠금 | `TestAdminLoginApi.test_lockout_flow`, `TestAdminLogin` |
| US-E7 | `validate_menu_input`, 필드별 422 | `test_security_schemas.TestValidation`, `TestCreate` |
| US-E9 | `Unauthorized` 401 + `WWW-Authenticate` | `TestTokenEnforcement` |

## backend-order에 넘기는 사항

1. `register_schema()`로 주문 관련 모듈 등록, 같은 `Database` 사용. `tables`는 이 Unit 소유(등록 API는 backend-order).
2. `MenuService.get_active_menus_by_ids`로 가격 재계산, 결과에 없는 ID는 `MENU_UNAVAILABLE`.
3. `AppError` 상속으로 `MENU_UNAVAILABLE`(409, `details.menuIds`), `PRICE_CHANGED`(409, `details.currentPrices`), `INVALID_TRANSITION`, `NO_ACTIVE_SESSION`, `DUPLICATE_TABLE`(409) 추가.
4. `create_app(event_publisher=...)` 또는 `MenuService.set_publisher`로 EventBroker 연결. 프론트엔드가 쓰는 `order_created` 이벤트에는 `payload.orderId` 포함.
5. 계약의 주문·테이블·SSE 경로를 구현하고 `tests/contract`에 해당 operation을 추가해 일치 확인. `clientOrderId` 멱등성과 대시보드 `table` 필터 규칙 준수.
6. SSE 라우터는 동기 서비스(스레드풀)에서 발행하는 이벤트를 이벤트 루프로 안전하게 전달해야 한다.
