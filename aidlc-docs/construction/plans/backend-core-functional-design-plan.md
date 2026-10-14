# Functional Design 계획 - backend-core (Unit 2)

대상 Unit: `backend-core` (기반 + 인증 + 메뉴). 구성: Config, Database, Security, Auth Deps, AuthService, MenuService, 인증/메뉴 라우터, App Entry(정적 서빙, 공통 오류 처리), 시드 스크립트.
참고: `unit-of-work.md`, `unit-of-work-story-map.md`(담당 스토리 13개: US-C1.1, C2.1, C2.2, A1.1, A1.2, A4.1~A4.4, E3, E4, E7, E9), `contracts/openapi.yaml`, `frontend/.../domain-entities.md`, `business-rules.md`(검증 값은 프론트엔드와 동일하게 사용), Application Design의 `components.md`, `services.md`

이 단계에서는 데이터 모델(스키마), 인증/잠금/토큰 규칙, 메뉴 규칙, 오류 매핑을 상세 설계합니다. 주문/세션/이력 스키마는 backend-order의 Functional Design에서 정의하되, `tables` 테이블은 이 Unit이 소유합니다.

아래 질문의 `[Answer]:` 뒤에 알파벳을 적어주세요. 맞는 선택지가 없으면 `X) Other`를 고르고 설명을 적어주세요. "추천해서 진행"이라고 적으셔도 됩니다.

---

## Part A. 질문

## Question 1
관리자 로그인 잠금(연속 5회 실패 → 15분)의 적용 단위는 무엇으로 할까요? (관리자 계정은 매장당 1개)

A) 계정 단위: 매장 식별자 + 사용자명 기준으로 집계 (어느 기기에서 시도하든 합산)

B) 클라이언트 IP 단위: 같은 IP에서의 연속 실패만 집계

C) 계정 단위와 IP 단위를 모두 적용 (둘 중 하나라도 초과하면 잠금)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
로그인 실패 횟수와 잠금 상태는 어디에 보관할까요?

A) SQLite 테이블에 저장 (서버를 재시작해도 잠금 유지)

B) 서버 메모리에만 저장 (재시작하면 초기화)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
테이블 로그인(비밀번호 숫자 4자리 = 10,000가지)에도 실패 제한을 적용할까요? (요구사항에는 관리자만 명시됨)

A) 적용: 같은 테이블 번호에 연속 10회 실패 시 5분간 로그인 차단

B) 적용하지 않음 (요구사항 범위만 구현)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
메뉴 삭제 방식은 어떻게 할까요? (주문 항목은 주문 시점의 메뉴명/단가를 복사해 저장하므로 삭제해도 과거 주문 표시에는 영향이 없습니다)

A) 물리 삭제 (행을 실제로 지움)

B) 소프트 삭제 (삭제 표시만 하고 조회에서 제외)

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
같은 카테고리 안에서 같은 이름의 메뉴를 허용할까요?

A) 허용하지 않음: 같은 카테고리 내 이름 중복이면 입력 검증 오류(422, `name` 필드)

B) 허용

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
카테고리의 표시 순서는 어떻게 정할까요? (카테고리는 별도 테이블 없이 메뉴의 문자열 값입니다)

A) 해당 카테고리가 처음 만들어진 순서 (그 카테고리의 첫 메뉴 등록 순서)

B) 가나다순

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
매장 식별자, 사용자명 비교는 대소문자를 구분할까요?

A) 구분함 (정확히 일치해야 함)

B) 구분하지 않음 (대소문자 무시, 앞뒤 공백은 제거)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 8
시드 스크립트(샘플 메뉴/테이블 생성)의 동작은 어떻게 할까요?

A) 데이터가 이미 있으면 건너뛰고(여러 번 실행해도 안전), `--reset` 옵션을 주면 초기화 후 다시 넣는다

B) 실행할 때마다 항상 추가한다

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 9
데이터베이스 스키마 초기화/변경 방식은 어떻게 할까요? (backend-order가 나중에 자기 테이블을 추가합니다)

A) 서버 시작 시 `CREATE TABLE IF NOT EXISTS`로 생성하고, `schema_version` 테이블로 버전을 기록한다 (Unit별 모듈이 자기 테이블을 등록)

B) `CREATE TABLE IF NOT EXISTS`만 사용 (버전 기록 없음)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## Part B. 별도 질문 없이 적용할 설계 가정 (이견이 있으면 알려주세요)

| # | 가정 |
|---|---|
| G1 | 설정은 `backend/.env`로 읽는다: `STORE_ID`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`(bcrypt), `JWT_SECRET`(최소 32자), `DB_PATH`(기본 `backend/data/table_order.sqlite3`). 필수값이 없거나 `JWT_SECRET`이 짧으면 서버가 시작되지 않는다(fail fast). `.env.example`과 해시 생성 스크립트(`scripts/hash_password.py`)를 제공한다. |
| G2 | JWT는 HS256. 클레임: `sub`, `role`(`admin`/`table`), `storeId`, 테이블 토큰은 `tableId`/`tableNumber` 추가, `iat`, `exp`(발급 후 16시간). 관리자/테이블 토큰은 `role`로 구분하며 서로의 API에 쓸 수 없다. |
| G3 | 테이블 비밀번호는 bcrypt 해시로만 저장한다. 비교는 상수 시간 비교(bcrypt 검증)를 사용한다. 관리자 비밀번호 검증도 bcrypt로 한다. |
| G4 | 로그인 실패 응답은 어느 항목이 틀렸는지 알리지 않는다(`INVALID_CREDENTIALS`). 존재하지 않는 테이블 번호도 비밀번호 불일치와 같은 응답을 준다. |
| G5 | 잠금 규칙: 성공 로그인 시 실패 횟수 초기화. 5번째 연속 실패 응답부터 429 `ACCOUNT_LOCKED`(`retryAfterSeconds` = 남은 초). 잠금 중에는 올바른 정보로도 거부(429). 잠금 시간 경과 후 첫 시도부터 다시 집계. |
| G6 | 시각은 UTC 기준 ISO 8601 문자열(`Z` 또는 오프셋 포함)로 저장/응답한다. |
| G7 | 메뉴 노출 순서(`display_order`)는 카테고리 내 1부터 연속 번호. 새 메뉴는 카테고리 맨 뒤. 카테고리를 바꿔 수정하면 새 카테고리 맨 뒤로 가고 이전 카테고리의 번호는 빈틈 없이 다시 매긴다. 순서 변경 요청은 해당 카테고리의 전체 ID가 정확히 한 번씩 포함되어야 한다(아니면 422). |
| G8 | 메뉴 입력 검증 값은 프론트엔드와 동일: 메뉴명 1~50, 설명 0~300, 카테고리 1~30(앞뒤 공백 제거), 가격 100~1,000,000 정수, 이미지 URL 선택(http/https). 위반 시 422 `VALIDATION_ERROR`와 필드별 사유. |
| G9 | 모든 오류 응답은 계약의 `ApiErrorBody`(`code`, `message`, `fields`, `retryAfterSeconds`, `details`) 형식이다. FastAPI 기본 422 형식은 이 형식으로 변환한다. 처리하지 못한 예외는 500 `INTERNAL_ERROR`(내부 정보 비노출, 서버 로그에는 기록). |
| G10 | 인증 의존성: `Authorization: Bearer` 누락/만료/위변조/잘못된 role은 401 `UNAUTHORIZED`. |
| G11 | SQLite 연결은 요청 단위로 생성하고 WAL 모드, `foreign_keys=ON`, `busy_timeout` 설정. 서비스는 동기 함수(FastAPI 스레드풀)로 구현한다. |
| G12 | 프론트엔드 빌드 산출물(`frontend/dist`)이 있으면 `/`와 비-API 경로에서 정적 서빙하고 SPA 폴백(`index.html`)을 제공한다. `/api/*`는 폴백 대상이 아니다(없는 API는 404 JSON). 같은 오리진이므로 CORS는 설정하지 않는다(개발 시 Vite 프록시 사용). |
| G13 | `MenuService`는 이벤트 발행기를 선택적으로 주입받는다(기본은 no-op). 메뉴 변경 성공 후(커밋 후) `menu_changed`를 발행한다. |
| G14 | 시드 데이터는 프론트엔드 mock 시드와 같은 내용(매장 `demo`, 테이블 1~5번 비밀번호 `1234`, 샘플 메뉴 12개)으로 한다. 개발용 값이며 운영에서는 사용하지 않는다. |
| G15 | Python 가상환경(`backend/.venv`)을 사용한다. 현재 시스템 Python은 3.14.4이며, 필요한 패키지의 휠이 없으면 호환되는 버전을 사용하도록 코드 생성 단계에서 조정하고 결과를 보고한다. |

---

## Part A-2. 답변 확정 (분석 결과)

직접 답변은 Q4뿐이고 나머지는 "추천해서 진행"으로 위임되어 AI 추천으로 확정했습니다. 충돌/모호성은 없습니다.

| 질문 | 확정 | 출처 | 근거 |
|---|---|---|---|
| Q1 잠금 단위 | 계정 단위. 관리자 계정이 1개뿐이므로 제출한 매장 식별자/사용자명과 무관하게 **하나의 관리자 잠금 키**로 집계 | 위임 -> 추천 A | 사용자명을 바꿔가며 잠금을 회피하는 시도를 막는다. IP 기반은 프록시/NAT 환경에서 부정확하다. 단점: 공격자가 의도적으로 관리자를 잠글 수 있음(로컬 단일 매장 환경에서 수용) |
| Q2 잠금 보관 | SQLite 테이블 | 위임 -> 추천 A | 서버 재시작으로 제한이 풀리지 않는다 |
| Q3 테이블 로그인 제한 | 적용: 같은 테이블 번호에 연속 10회 실패 시 5분 차단 | 위임 -> 추천 A | 비밀번호가 4자리(1만 가지)라 무제한 시도에 취약하다. 요구사항에 없는 추가 보호이므로 아래 "계약 영향"을 참고 |
| Q4 메뉴 삭제 | **소프트 삭제** | 사용자 답변 B | - |
| Q5 이름 중복 | 같은 카테고리 내 중복 불가(422, `name`). 삭제된 메뉴는 제외하고 검사 | 위임 -> 추천 A | 고객 화면에서 동일 이름 혼동 방지. 소프트 삭제와 맞물려 "삭제되지 않은 메뉴만" 유일성 적용 |
| Q6 카테고리 순서 | 카테고리가 처음 만들어진 순서. 메뉴마다 `category_order`를 저장해 안정적으로 유지 | 위임 -> 추천 A | 메뉴가 삭제되어도 다른 카테고리의 순서가 흔들리지 않는다 |
| Q7 대소문자 | 구분함 (앞뒤 공백 제거 후 정확히 일치) | 위임 -> 추천 A | 단순하고 모호함이 없다 |
| Q8 시드 | 데이터가 이미 있으면 건너뜀, `--reset`으로 초기화 후 재삽입 | 위임 -> 추천 A | 반복 실행 안전 |
| Q9 스키마 | `CREATE TABLE IF NOT EXISTS` + `schema_version`(모듈별 버전 기록), 모듈이 자기 스키마를 등록 | 위임 -> 추천 A | backend-order가 자기 테이블을 안전하게 추가할 수 있다 |

### 계약/다른 Unit 영향
- **Q3 -> 계약 수정**: `contracts/openapi.yaml`의 `POST /api/customer/auth/login`에 `429 ACCOUNT_LOCKED` 응답을 추가한다 (이 단계에서 반영). 프론트엔드 코드 변경은 필요 없다: `TableAuthProvider`가 기타 오류를 `error` 상태로 표시하고 `messageForError`의 `ACCOUNT_LOCKED` 문구를 보여준다. 잠금 중 5초 자동 재시도는 잠금 상태에서 실패 횟수를 늘리지 않으므로 해롭지 않다.
- **Q4 -> backend-order**: 주문 항목은 메뉴명/단가를 복사 저장하므로 메뉴 삭제와 무관. 주문 생성 시 삭제된 메뉴는 `MENU_UNAVAILABLE`로 처리해야 한다 (`MenuService.get_active_menus_by_ids`가 삭제된 메뉴를 제외해 반환).

---

## Part C. 실행 체크리스트 (답변 확정 후 수행)

### 분석
- [x] A1. unit-of-work.md, 스토리 맵(13개 스토리), 계약 중 인증/메뉴 경로 재확인
- [x] A2. 답변 분석 및 모호성 해소 (Q4 외 위임 -> 추천 확정, 충돌 없음)

### 산출물 생성 (`aidlc-docs/construction/backend-core/functional-design/`)
- [x] D1. `domain-entities.md`: 테이블 정의(menus, tables, login_attempts, schema_version), 제약, 인덱스, 설정 모델, 토큰 클레임
- [x] D2. `business-logic-model.md`: 관리자 로그인, 테이블 로그인, 토큰 검증, 메뉴 조회/등록/수정/삭제/순서 변경, 시드, 시작 시 초기화 흐름
- [x] D3. `business-rules.md`: 검증 규칙, 잠금 규칙, 비밀번호 정책, 순서 규칙, 오류 매핑 표(예외 -> HTTP 상태 -> 코드)
- [x] D4. 계약(`contracts/openapi.yaml`)의 backend-core 경로(4개 라우터 8개 operation)와 설계 일치 검증 (customer login 429 누락 발견 -> 계약 수정)
- [x] D5. 담당 스토리 13개 반영 여부 검증

### 마무리
- [x] F1. `aidlc-state.md`, `audit.md` 갱신
- [ ] F2. 완료 메시지 제시 및 사용자 승인 대기
