# Business Rules - backend-core (Unit 2)

확정 답변: `backend-core-functional-design-plan.md` Q1~Q9(Q4만 사용자 답변, 나머지는 위임 -> AI 추천)와 가정 G1~G15.

## 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 관리자 잠금 | 연속 5회 실패 -> 15분. 계정 단위(관리자 1개 키로 집계), SQLite 저장 |
| 테이블 로그인 제한 | 같은 테이블 번호 연속 10회 실패 -> 5분 (요구사항 외 추가 보호) |
| 메뉴 삭제 | 소프트 삭제 (`deleted_at`) |
| 메뉴 이름 중복 | 같은 카테고리의 활성 메뉴 간 불가 (422 `name`) |
| 카테고리 순서 | 처음 만들어진 순서, 메뉴마다 `category_order`로 안정 유지 |
| 식별자 비교 | 대소문자 구분, 앞뒤 공백 제거 후 정확 일치 |
| 시드 | 데이터가 있으면 건너뜀, `--reset`으로 초기화 |
| 스키마 | `CREATE TABLE IF NOT EXISTS` + `schema_version` 모듈별 기록 |

---

## 1. 입력 검증 규칙

공통: 문자열 입력은 앞뒤 공백을 제거한 뒤 검사한다 (비밀번호는 제외). 위반 시 모든 필드 오류를 모아 한 번에 422 `VALIDATION_ERROR`(`fields`)로 응답한다. 오류 문구는 프론트엔드 `business-rules.md`와 동일하다.

| 대상 | 필드 | 규칙 | 오류 문구 (`fields[필드]`) |
|---|---|---|---|
| 테이블 로그인 | storeId | 1~50자 | 매장 식별자를 입력해주세요. |
| | tableNumber | 정수 1~999 | 테이블 번호는 1~999 사이 숫자로 입력해주세요. |
| | password | `^\d{4}$` | 비밀번호는 숫자 4자리입니다. |
| 관리자 로그인 | storeId, username | 비어 있지 않음 | 해당 항목을 입력해주세요. |
| | password | 비어 있지 않음, 72바이트 이하 (bcrypt 한계) | 해당 항목을 입력해주세요. |
| 메뉴 | name | 1~50자 | 메뉴명은 1~50자로 입력해주세요. |
| | price | 정수, 100 이상 1,000,000 이하 | 가격은 100원~1,000,000원 사이 정수로 입력해주세요. |
| | description | 0~300자 | 설명은 300자 이내로 입력해주세요. |
| | category | 1~30자 | 카테고리는 1~30자로 입력해주세요. |
| | imageUrl | 선택(null 또는 빈 문자열은 없음으로 처리). 값이 있으면 `http`/`https` 스킴과 호스트를 가진 유효한 URL, 2048자 이하 | 이미지 주소는 http 또는 https URL이어야 합니다. |
| | name (중복) | 같은 카테고리 활성 메뉴 중 같은 이름이 있으면 불가 (수정 시 자기 자신 제외) | 같은 카테고리에 같은 이름의 메뉴가 이미 있어요. |
| 순서 변경 | category | 활성 메뉴가 있는 카테고리 (없으면 404) | - |
| | orderedIds | 해당 카테고리 활성 메뉴 ID 전체가 정확히 한 번씩 | 해당 카테고리의 모든 메뉴 ID가 필요해요. |

- JSON 타입이 틀린 입력(문자열 가격 등)도 `VALIDATION_ERROR`로 변환한다 (해당 필드에 같은 필드 문구).
- 본문이 JSON이 아니거나 필수 키가 없으면 422, `fields`에 누락된 키를 표시한다.

---

## 2. 인증 규칙

### 2.1 관리자 로그인
1. 입력 검증 (422).
2. **잠금 확인**: `login_attempts(admin, account)`의 `locked_until`이 현재보다 미래면 `AccountLocked(남은 초)` (429). 올바른 정보로도 거부한다.
3. 잠금 시간이 지났다면 행을 초기화(실패 0, locked_until NULL)한다.
4. 자격 증명 확인: `storeId`와 `username`이 설정과 정확히 일치하고 `password`가 `ADMIN_PASSWORD_HASH`와 bcrypt로 일치. 어느 하나라도 틀리면 실패. (항목별로 어느 것이 틀렸는지 구분하지 않는다. 비교 시간 차이를 줄이기 위해 매장/사용자명이 틀려도 비밀번호 해시 검증을 수행한다.)
5. 실패: `failure_count += 1`. `failure_count >= 5`이면 `locked_until = now + 15분`, `failure_count = 0`으로 저장하고 `AccountLocked(900)` (429). 그 미만이면 `InvalidCredentials` (401).
6. 성공: 행의 실패 횟수/잠금을 초기화하고 토큰 발급(200).

잠금 계산:
- 5번째 연속 실패 **응답부터** 429를 반환한다 (US-E4).
- `retryAfterSeconds = ceil(locked_until - now)` (최소 1).
- 실패 횟수 갱신은 `BEGIN IMMEDIATE` 트랜잭션에서 읽기-수정-쓰기로 수행해 동시 요청이 횟수를 덮어쓰지 않게 한다.

### 2.2 테이블 로그인
1. 입력 검증 (422).
2. `storeId`가 설정과 정확히 일치하지 않으면 `InvalidCredentials` (401). (이 경우 실패 횟수는 집계하지 않는다 - 존재하지 않는 테이블과 동일 취급)
3. `table_number`로 테이블 조회. **없으면** 더미 해시로 bcrypt 검증을 한 번 수행해 응답 시간을 맞춘 뒤 `InvalidCredentials` (401). 집계하지 않는다.
4. 테이블이 있으면 `login_attempts(table, <번호>)` 잠금 확인. 잠겨 있으면 `AccountLocked` (429).
5. 비밀번호 bcrypt 검증. 실패 시 `failure_count += 1`, 10 이상이면 5분 잠금(429), 아니면 401. 성공 시 초기화 후 토큰 발급.
6. 잠금 확인은 "테이블이 존재하는 경우에만" 적용되므로, 존재하지 않는 번호로는 잠금 정보를 얻을 수 없다.

### 2.3 토큰 검증 (Auth Deps)
- `Authorization: Bearer <token>` 필수. 누락, 형식 오류, 서명 불일치, 만료, `role` 불일치, `storeId` 불일치 -> `Unauthorized` (401 `UNAUTHORIZED`).
- `require_admin`: `role=admin`. `require_table`: `role=table`이며 `tableId`의 테이블이 DB에 존재해야 한다.
- 만료 직후 요청도 401이며 프론트엔드가 재로그인/로그아웃을 처리한다 (US-E9).
- 로그인 엔드포인트는 인증 의존성이 없다.

### 2.4 비밀번호 처리
- 테이블 비밀번호는 bcrypt 해시만 저장한다 (cost = `BCRYPT_ROUNDS`).
- 비밀번호/해시/토큰/JWT 시크릿은 로그와 오류 응답에 남기지 않는다.
- 관리자 비밀번호 입력이 72바이트를 넘으면 검증 단계에서 거부한다(bcrypt 절단 방지).

---

## 3. 메뉴 규칙

### 3.1 조회 (고객/관리자 공용)
- 활성 메뉴(`deleted_at IS NULL`)만. `category_order` 오름차순으로 카테고리, 각 카테고리 안에서 `display_order` 오름차순.
- 활성 메뉴가 없는 카테고리는 응답에 나타나지 않는다. 메뉴가 하나도 없으면 빈 배열.
- 고객 조회는 테이블 토큰, 관리자 조회는 관리자 토큰이 필요하다 (같은 서비스 메서드).

### 3.2 등록
1. 입력 검증, 중복 이름 검사.
2. 카테고리 결정: 활성 메뉴 중 같은 `category`가 있으면 그 `category_order`를 사용, 없으면 `(활성 메뉴의 최대 category_order) + 1` (없으면 1).
3. `display_order = (해당 카테고리 활성 메뉴 최대값) + 1` (없으면 1).
4. 삽입, `created_at = updated_at = now`. 201과 생성된 `Menu` 반환.
5. 커밋 후 `menu_changed` 이벤트 발행(주입된 경우).

### 3.3 수정
1. 활성 메뉴가 아니면 404.
2. 입력 검증, 중복 이름 검사 (자기 자신 제외).
3. 카테고리가 바뀌면: 새 카테고리 기준으로 `category_order`/`display_order`를 3.2와 같이 정하고(맨 뒤), 이전 카테고리의 남은 활성 메뉴 `display_order`를 현재 순서대로 1..N으로 다시 매긴다.
4. 카테고리가 같으면 순서는 유지한다.
5. `updated_at = now`. 200과 수정된 `Menu` 반환. 커밋 후 `menu_changed`.

### 3.4 삭제 (소프트)
1. 활성 메뉴가 아니면 404 (이미 삭제된 메뉴 재삭제 포함).
2. `deleted_at = now`, `updated_at = now`.
3. 같은 카테고리 남은 활성 메뉴의 `display_order`를 1..N으로 다시 매긴다.
4. 204 반환. 커밋 후 `menu_changed`.
- 삭제된 메뉴 이름은 재사용 가능 (유일성 인덱스가 활성 메뉴만 대상).
- 삭제된 메뉴 ID는 주문 생성 시 `MENU_UNAVAILABLE`로 취급된다 (backend-order가 `get_active_menus_by_ids`로 판단).

### 3.5 순서 변경
1. 카테고리에 활성 메뉴가 없으면 404.
2. `orderedIds`가 해당 카테고리 활성 메뉴 ID 집합과 정확히 같지 않으면(누락, 초과, 중복, 다른 카테고리 ID) 422 `orderedIds`.
3. 목록 순서대로 `display_order = 1..N`. `category_order`는 바뀌지 않는다.
4. 204. 커밋 후 `menu_changed`.

### 3.6 다른 Unit을 위한 조회
- `MenuService.get_active_menus_by_ids(ids) -> dict[int, Menu]`: 활성 메뉴만 반환 (backend-order의 OrderService가 가격 재계산에 사용).

---

## 4. 오류 매핑 (예외 -> HTTP)

| 예외 / 상황 | HTTP | `code` | 본문 추가 필드 |
|---|---|---|---|
| `ValidationFailed` | 422 | `VALIDATION_ERROR` | `fields` |
| FastAPI/Pydantic 요청 검증 오류 | 422 | `VALIDATION_ERROR` | `fields` (위치 `body.xxx` -> `xxx`) |
| `InvalidCredentials` | 401 | `INVALID_CREDENTIALS` | - |
| `Unauthorized` | 401 | `UNAUTHORIZED` | - (`WWW-Authenticate: Bearer` 헤더) |
| `AccountLocked` | 429 | `ACCOUNT_LOCKED` | `retryAfterSeconds` (+ `Retry-After` 헤더) |
| `NotFound` | 404 | `NOT_FOUND` | - |
| 존재하지 않는 `/api/*` 경로 | 404 | `NOT_FOUND` | - |
| 허용되지 않는 메서드 (`/api/*`) | 404 | `NOT_FOUND` | - (정적 서빙 폴백 라우트가 모든 메서드를 받아 JSON 404로 응답하므로 405는 발생하지 않는다. 코드 집합을 늘리지 않으려는 의도와도 일치) |
| 처리되지 않은 예외 | 500 | `INTERNAL_ERROR` | 내부 정보 비노출, 서버 로그에 스택 기록 |

모든 오류 응답 본문은 `ApiErrorBody` 형식이며 `message`는 사용자에게 보여줘도 되는 짧은 한국어 문구다 (프론트엔드는 `code`로 문구를 정한다).

---

## 5. 시드 규칙 (`scripts/seed.py`)

- 대상: 테이블 1~5번(비밀번호 `1234`, bcrypt 해시 저장), 샘플 메뉴 12개 (메인 4, 사이드 3, 음료 4, 디저트 1 - 프론트엔드 mock 시드와 동일한 이름/가격/설명). 매장 식별자 `demo`는 `.env.example`의 `STORE_ID`로 안내한다.
- 기본 동작: 스키마 초기화 후, `tables`와 `menus`가 **둘 다 비어 있을 때만** 삽입한다. 하나라도 데이터가 있으면 아무것도 하지 않고 "이미 데이터가 있어 건너뜀"을 출력한다.
- `--reset`: 스키마 외 모든 앱 테이블(`schema_version`, `sqlite_*` 제외)의 데이터를 삭제한 뒤 다시 삽입한다. 실행 전 대상 DB 경로를 출력하고 `--yes`가 없으면 확인 프롬프트를 띄운다.
- 개발용 값이며 운영에서는 사용하지 않는다고 스크립트 도움말에 표시한다.

## 6. 시작 시 규칙

1. 설정 로드/검증 (실패하면 종료).
2. DB 디렉토리 생성, 연결 설정(WAL, `foreign_keys=ON`, `busy_timeout=5000`).
3. 스키마 초기화: 등록된 모듈 스키마(`core`)를 순서대로 `CREATE ... IF NOT EXISTS`로 적용하고 `schema_version`을 기록. 저장된 버전이 코드가 아는 버전보다 높으면 시작을 거부한다(다운그레이드 방지).
4. 라우터 등록, 오류 핸들러 등록.
5. `FRONTEND_DIST`가 있으면 정적 서빙 + SPA 폴백(`/api/*` 제외) 등록. 없으면 API만 제공하고 안내 로그를 남긴다.
