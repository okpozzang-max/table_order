# Code Generation Plan - backend-core (Unit 2)

이 문서는 Unit 2 `backend-core`의 Code Generation 단일 기준 문서입니다. 승인 후 Step 순서대로 생성하며, 각 Step 완료 즉시 체크박스를 `[x]`로 갱신합니다.

## Unit 컨텍스트

- **입력 설계**: `aidlc-docs/construction/backend-core/functional-design/` (domain-entities, business-logic-model, business-rules), `aidlc-docs/inception/application-design/`, 계약 `contracts/openapi.yaml`
- **구현 스토리 (13개)**: US-C1.1, C2.1, C2.2, A1.1, A1.2, A4.1, A4.2, A4.3, A4.4, E3, E4, E7, E9
- **의존성**: 다른 Unit 코드에 의존하지 않음. 계약(`contracts/openapi.yaml`)을 구현하고 일치 여부를 테스트로 검증
- **소유 산출물**: `backend/` 기반 코드, 인증·메뉴 API, 시드 스크립트, 스키마 `core` 모듈(menus, tables, login_attempts, schema_version)
- **코드 위치**: 워크스페이스 루트 `C:\Users\okpoz\AWS\table_order\backend\` (문서는 aidlc-docs에 요약만)
- **환경**: Python 3.14.4, pip 26.1 (Docker 미사용). PyPI에서 확인한 최신 버전: fastapi 0.143.0, uvicorn 0.54.0, pydantic 2.14.1, pydantic-settings 2.15.0, bcrypt 5.0.0, PyJWT 2.15.1, pytest 9.1.1, httpx 0.28.1, PyYAML 6.0.3. 모두 `==`로 고정한다. 3.14 휠 문제가 생기면 호환 버전으로 조정하고 요약에 기록한다
- **자동화 규칙**: UI가 없으므로 `data-testid` 규칙은 해당 없음

## 구현 방침 (설계에서 정한 사항의 코드 수준 결정)

| 항목 | 결정 |
|---|---|
| 요청 검증 | Pydantic 모델(`Field` 제약, `strip_whitespace`)로 규칙을 표현하고, `RequestValidationError`를 필드명 -> 한국어 문구 표로 `ApiErrorBody(fields)`에 매핑. 이렇게 하면 OpenAPI 요청 스키마가 계약과 가까워진다 |
| 서비스 | 동기 함수. `Database`가 요청 단위 연결과 `BEGIN IMMEDIATE` 트랜잭션 컨텍스트를 제공. 시각은 주입 가능한 `clock` |
| 토큰 만료 판정 | PyJWT의 `exp` 자동 검증 대신 주입된 `clock`으로 직접 검사 (테스트에서 시간 이동 가능) |
| 인증 의존성 | `HTTPBearer(auto_error=False)`를 `tableBearer`/`adminBearer` 이름으로 사용해 OpenAPI 보안 스킴을 계약과 맞추고, 오류는 직접 `Unauthorized`로 변환 |
| 이벤트 | `EventPublisher` 프로토콜 + `NullPublisher` 기본. backend-order가 실제 구현을 연결 |
| 실행 | `python -m uvicorn app.main:create_app --factory` (모듈 import 시 환경 변수를 요구하지 않음) |
| JSON 키 | 응답/요청은 camelCase (Pydantic alias), DB는 snake_case |

---

## 생성 단계

### Step 1. 프로젝트 스캐폴드와 가상환경
- [x] `backend/requirements.txt`(런타임), `backend/requirements-dev.txt`(pytest, httpx, PyYAML), 모두 `==` 고정
- [x] `backend/pytest.ini` (`pythonpath = .`, `testpaths = tests`), `backend/.env.example` (개발용 값, 해시는 Step 12의 스크립트로 생성한 값), `backend/.gitignore` 보강(`.venv/`, `.env`, `data/`)
- [x] 패키지 디렉토리: `backend/app/{__init__,services/__init__,routers/__init__}.py`, `backend/scripts/`, `backend/tests/`
- [x] `python -m venv backend/.venv` 생성 후 의존성 설치, 설치 결과(버전) 확인

### Step 2. 도메인 예외와 오류 응답 (`app/errors.py`)
- [x] 도메인 예외: `ValidationFailed(fields)`, `InvalidCredentials`, `Unauthorized`, `AccountLocked(retry_after_seconds)`, `NotFound`
- [x] 오류 -> `ApiErrorBody` 변환 함수, 필드 문구 표(`FIELD_MESSAGES`)
- [x] 단위 테스트: 변환 결과 형식
- **스토리**: US-E3, E4, E7, E9

### Step 3. 설정 (`app/config.py`)
- [x] `Settings`(pydantic-settings, `.env`): 키/기본값/검증은 domain-entities 2절. 오류 메시지는 키 이름만 노출(값 비노출), `get_settings()`
- [x] 단위 테스트: 필수 누락, `JWT_SECRET` 짧음, 해시 형식 오류, 숫자 설정 검증, 기본값
- **스토리**: US-A1.1(설정 기반 계정)

### Step 4. 데이터베이스와 스키마 레지스트리 (`app/db.py`, `app/schema_core.py`)
- [x] `Database`: 파일 경로 준비, `connect()`(WAL, `foreign_keys=ON`, `busy_timeout=5000`, `row_factory`), `transaction(immediate=True)` 컨텍스트(커밋/롤백)
- [x] `register_schema()`, `init_schema()`: `schema_version` 기록, 저장 버전이 코드보다 높으면 시작 거부
- [x] `schema_core.py`: `menus`, `tables`, `login_attempts` DDL(인덱스 포함), 모듈 `core` v1 등록
- [x] 단위 테스트: 스키마 생성 멱등, 유니크 인덱스(활성 메뉴만), 체크 제약, 버전 거부, 트랜잭션 롤백
- **스토리**: 기반 (전체)

### Step 5. 보안 (`app/security.py`)
- [x] `hash_password`/`verify_password`(bcrypt, rounds 설정, 72바이트 처리, 더미 해시), `create_token`/`decode_token`(HS256, 클레임: sub, role, storeId, tableId, tableNumber, iat, exp; `clock` 주입, 수동 만료 검사)
- [x] 단위 테스트: 해시/검증, 변조/만료/잘못된 role 거부, 클레임 내용
- **스토리**: US-A1.1, A1.2, E9

### Step 6. 스키마 모델 (`app/schemas.py`)
- [x] Pydantic 모델(camelCase alias): `TableLoginRequest`, `AdminLoginRequest`, `TokenResponse`, `TableTokenResponse`, `Menu`, `CategoryMenus`, `MenuInput`(문자열 strip, 길이/범위, URL 검증), `ReorderRequest`, `ApiErrorBody`
- [x] 단위 테스트: 경계값(메뉴명 50/51, 가격 99/100/1,000,000/1,000,001, 설명 300/301, 카테고리 30/31, URL 스킴, 비밀번호 4자리, 테이블 번호 1~999)
- **스토리**: US-E7, E3

### Step 7. 이벤트 포트 (`app/events_port.py`)
- [x] `ServerEvent`, `EventPublisher` 프로토콜, `NullPublisher`

### Step 8. AuthService (`app/services/auth_service.py`)
- [x] `login_admin`, `login_table`: business-logic-model 3, 4절 그대로 (잠금, 카운트, 더미 해시, 커밋 후 예외, `BEGIN IMMEDIATE`)
- [x] 단위 테스트(주입 clock): 성공, 틀린 정보, 4회 실패 후 5번째에서 429(900초), 잠금 중 올바른 정보 거부, 잠금 만료 후 성공과 카운트 초기화, 사용자명을 바꿔도 같은 잠금, 서버 재시작(새 Database 인스턴스) 후에도 잠금 유지, 테이블 10회/5분 규칙, 존재하지 않는 테이블/매장 불일치는 집계 안 함
- **스토리**: US-C1.1, A1.1, A1.2, E3, E4

### Step 9. MenuService (`app/services/menu_service.py`)
- [x] `list_grouped`, `create`, `update`, `delete`(소프트), `reorder`, `get_active_menus_by_ids`, 이벤트 발행기 선택 주입(커밋 후 발행)
- [x] 단위 테스트: 순서/카테고리 규칙(새 카테고리 order, 맨 뒤 추가, 카테고리 이동 시 재번호), 소프트 삭제 후 이름 재사용·조회 제외·재번호, 중복 이름 422, 순서 변경 집합 검증, 발행 시점(커밋 후, 실패 시 미발행), 삭제된 ID는 `get_active_menus_by_ids`에서 제외
- **스토리**: US-C2.1, C2.2, A4.1~A4.4, E7

### Step 10. 인증 의존성과 라우터
- [x] `app/deps.py`: 컨테이너(settings, db, services, clock) 접근, `require_admin`, `require_table`(DB 존재 확인)
- [x] `app/routers/customer_auth.py`, `customer_menu.py`, `admin_auth.py`, `admin_menus.py` (`/api/admin/menus/reorder`를 `/{menu_id}`보다 먼저 등록)
- [x] 라우터 -> 서비스 호출, 상태 코드(201, 204), `Retry-After`/`WWW-Authenticate` 헤더
- **스토리**: US-C1.1, C2.1, C2.2, A1.1, A1.2, A4.1~A4.4, E3, E4, E7, E9

### Step 11. 앱 조립 (`app/main.py`)
- [x] `create_app(settings=None, clock=None, event_publisher=None)`: lifespan에서 설정/DB/스키마 초기화, 서비스 구성, 라우터 등록
- [x] 오류 핸들러: 도메인 예외, `RequestValidationError`(필드 매핑), `HTTPException`(404/405 -> `NOT_FOUND`), 일반 예외 -> 500 `INTERNAL_ERROR`(로그 기록, 내부 정보 비노출)
- [x] 정적 서빙: `FRONTEND_DIST`가 있으면 정적 파일 + SPA 폴백(`/api/*` 제외), 없으면 안내 로그
- **스토리**: 기반, US-E9

### Step 12. 스크립트
- [x] `scripts/hash_password.py`: 비밀번호를 입력받아 bcrypt 해시 출력(입력은 프롬프트 또는 인자, 인자는 셸 기록 위험 안내)
- [x] `scripts/seed.py`: 멱등 시드, `--reset`/`--yes`, 대상 DB 경로 출력 (business-rules 5절)
- [x] 단위 테스트: 시드 멱등, `--reset`, 해시 스크립트 출력 형식

### Step 13. API 통합 테스트 (`tests/api/`)
- [x] 로그인 흐름(관리자/테이블), 잠금(429, `retryAfterSeconds`, `Retry-After`), 토큰 만료(clock 이동) -> 401, 잘못된 role의 토큰 -> 401, 삭제된 테이블 토큰 -> 401
- [x] 메뉴: 조회(고객/관리자), 등록 201, 수정, 소프트 삭제 204와 조회 제외, 순서 변경 204, `/reorder` 라우팅 우선, 검증 오류 형식(`fields`), 중복 이름, 404
- [x] 공통 오류 형식: 없는 `/api/*` 경로 404 JSON, 405, 처리되지 않은 예외 500(내부 정보 비노출), JSON 아닌 본문 422
- [x] 정적 서빙: `index.html` 제공, SPA 경로 폴백, `/api/*`는 폴백 제외
- **스토리**: 13개 전체

### Step 14. 계약 일치 테스트 (`tests/contract/`)
- [x] `contracts/openapi.yaml`을 읽어 backend-core의 8개 operation에 대해 앱의 OpenAPI와 비교: 경로/메서드 존재, 계약의 성공 상태 코드, 보안 요구 유무, 요청 스키마의 필드/필수 목록, 응답 스키마의 속성 이름, 앱이 사용하는 오류 상태 코드가 계약에 정의된 코드의 부분집합인지
- [x] 실제 응답 본문이 계약의 필수 필드를 모두 포함하는지 샘플 호출로 확인

### Step 15. 스모크 검증
- [x] `pytest` 전체 실행
- [x] 실제 서버 기동(`uvicorn --factory`, 임시 DB와 임시 `.env` 값) -> 시드 -> HTTP로 로그인/메뉴 조회/정적 `index.html` 확인(프론트엔드 `dist` 사용) -> 서버 종료, 임시 파일 정리
- [x] 결과를 코드 요약에 기록 (상세 지침은 Build and Test 단계)

### Step 16. 문서화
- [x] `backend/README.md`: 설치, 설정(.env), 해시 생성, 시드, 실행, 테스트, 디렉토리 구조, backend-order 연동 지점
- [x] `aidlc-docs/construction/backend-core/code/code-summary.md`

### Step 17. 스토리 추적성 확인
- [x] 13개 스토리의 구현/테스트 위치를 요약 문서 표에 기록, 계획서의 스토리 체크리스트 갱신

---

## 스토리 구현 체크리스트 (Step 완료 시 `[x]`)

[x] US-C1.1 [x] US-C2.1 [x] US-C2.2 [x] US-A1.1 [x] US-A1.2 [x] US-A4.1 [x] US-A4.2 [x] US-A4.3 [x] US-A4.4 [x] US-E3 [x] US-E4 [x] US-E7 [x] US-E9

## 범위 외 (이 Unit에서 하지 않는 것)
- 테이블 등록 API, 주문, 세션, 이력, SSE 엔드포인트, EventBroker (backend-order)
- Docker/배포 산출물 (Infrastructure Design 생략)
- 브라우저 E2E (Plan Q6: A에 따라 제외), 프론트엔드와의 실제 연결 검증 (Unit 3 이후 통합 단계)

## 규모 예상
- 17단계, 신규 파일 약 45~55개 (소스 약 18, 테스트 약 18, 설정/문서 약 10)
