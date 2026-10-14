# Domain Entities - backend-core (Unit 2)

저장소: SQLite 파일 1개. 시각은 모두 UTC ISO 8601 문자열(`2026-10-14T05:00:00Z` 형식)로 `TEXT`에 저장한다. 금액은 원 단위 `INTEGER`.

이 Unit이 소유하는 테이블: `schema_version`, `menus`, `tables`, `login_attempts`. 주문/세션/이력 테이블은 backend-order가 스키마 확장으로 추가한다.

---

## 1. 스키마

### 1.1 schema_version
모듈별 스키마 버전을 기록한다. 각 Unit의 스키마 모듈이 자기 이름으로 등록한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| module | TEXT | PK | `core`, 이후 `order` 등 |
| version | INTEGER | NOT NULL | 적용된 스키마 버전 |
| applied_at | TEXT | NOT NULL | 적용 시각 |

### 1.2 menus

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 메뉴 ID (삭제 후에도 재사용하지 않음) |
| name | TEXT | NOT NULL | 1~50자 (앞뒤 공백 제거 후 저장) |
| price | INTEGER | NOT NULL, CHECK 100 <= price <= 1000000 | 원 |
| description | TEXT | NOT NULL DEFAULT '' | 0~300자 |
| category | TEXT | NOT NULL | 1~30자 (앞뒤 공백 제거 후 저장) |
| category_order | INTEGER | NOT NULL | 카테고리 표시 순서. 같은 카테고리의 활성 메뉴는 모두 같은 값 |
| display_order | INTEGER | NOT NULL | 카테고리 내 노출 순서 (활성 메뉴 기준 1부터 연속) |
| image_url | TEXT | NULL | http/https URL 또는 NULL |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | NULL | NULL이면 활성, 값이 있으면 소프트 삭제됨 |

인덱스/제약:
- `UNIQUE INDEX ux_menus_category_name ON menus(category, name) WHERE deleted_at IS NULL` - 활성 메뉴 간 같은 카테고리 내 이름 중복 방지
- `INDEX ix_menus_active_order ON menus(category_order, display_order) WHERE deleted_at IS NULL`

불변식:
1. 활성 메뉴의 `display_order`는 카테고리마다 1..N 연속이고 중복이 없다.
2. 같은 카테고리의 활성 메뉴는 `category_order`가 모두 같고, 서로 다른 카테고리는 다르다.
3. 삭제된 메뉴는 어떤 조회/검증/순서 계산에도 포함되지 않는다.

### 1.3 tables

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | INTEGER | PK AUTOINCREMENT | 테이블 ID |
| table_number | INTEGER | NOT NULL UNIQUE, CHECK 1 <= n <= 999 | 화면 표시 번호 |
| password_hash | TEXT | NOT NULL | bcrypt 해시 (평문 저장 금지) |
| created_at | TEXT | NOT NULL | |

- 세션 상태(활성 세션 등)는 backend-order의 `table_sessions`가 가진다. `TableInfo.sessionActive`는 그쪽에서 계산한다.
- 이 Unit에서는 시드 스크립트가 테이블을 만든다. 등록 API(`POST /api/admin/tables`)는 backend-order가 제공한다.
- 매장은 1개이므로 `store_id` 컬럼은 두지 않는다. 매장 식별자는 설정(`STORE_ID`)과 비교만 한다.

### 1.4 login_attempts
로그인 연속 실패 횟수와 잠금 상태.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| scope | TEXT | PK(복합) | `admin` 또는 `table` |
| key | TEXT | PK(복합) | admin: 고정값 `account`, table: 테이블 번호 문자열 |
| failure_count | INTEGER | NOT NULL DEFAULT 0 | 연속 실패 횟수 (성공 시 행 삭제 또는 0) |
| locked_until | TEXT | NULL | 이 시각까지 잠금. NULL이면 잠금 아님 |
| updated_at | TEXT | NOT NULL | |

- 관리자 계정은 하나이므로 제출된 사용자명과 무관하게 `admin/account` 한 행으로 집계한다.
- 테이블 키는 **존재하는 테이블 번호에 대해서만** 행을 만든다 (임의 번호로 행이 무한히 늘어나는 것을 방지).

---

## 2. 설정 모델 (Settings)

`backend/.env` 또는 환경변수에서 로드한다.

| 키 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `STORE_ID` | 예 | - | 매장 식별자 (1~50자) |
| `ADMIN_USERNAME` | 예 | - | 관리자 사용자명 |
| `ADMIN_PASSWORD_HASH` | 예 | - | 관리자 비밀번호 bcrypt 해시 (`$2b$...`) |
| `JWT_SECRET` | 예 | - | 32자 이상 |
| `DB_PATH` | 아니오 | `backend/data/table_order.sqlite3` | SQLite 파일 경로 (상위 디렉토리는 자동 생성) |
| `TOKEN_TTL_HOURS` | 아니오 | 16 | 토큰 유효 시간 |
| `ADMIN_LOGIN_MAX_FAILURES` | 아니오 | 5 | 연속 실패 허용 횟수 |
| `ADMIN_LOGIN_LOCK_MINUTES` | 아니오 | 15 | 잠금 시간 |
| `TABLE_LOGIN_MAX_FAILURES` | 아니오 | 10 | |
| `TABLE_LOGIN_LOCK_MINUTES` | 아니오 | 5 | |
| `BCRYPT_ROUNDS` | 아니오 | 12 | 테스트에서는 낮춰서 사용 |
| `FRONTEND_DIST` | 아니오 | `frontend/dist` | 정적 서빙 디렉토리 (없으면 서빙 생략) |

시작 시 검증: 필수값 누락, `JWT_SECRET` 32자 미만, `ADMIN_PASSWORD_HASH`가 bcrypt 형식이 아님, 숫자 설정이 양의 정수가 아님 -> 서버가 시작되지 않고 어떤 키가 문제인지 알리는 메시지를 출력한다 (값 자체는 출력하지 않는다).

---

## 3. 토큰 (JWT, HS256)

| 클레임 | 관리자 토큰 | 테이블 토큰 |
|---|---|---|
| `sub` | `admin:<username>` | `table:<tableId>` |
| `role` | `admin` | `table` |
| `storeId` | 설정 매장 식별자 | 설정 매장 식별자 |
| `tableId` | - | 테이블 ID |
| `tableNumber` | - | 테이블 번호 |
| `iat` | 발급 시각 | 발급 시각 |
| `exp` | iat + 16시간 | iat + 16시간 |

- 응답의 `expiresAt`은 `exp`를 ISO 8601로 변환한 값이다.
- 검증: 서명, 만료, `role` 일치, `storeId`가 설정과 일치하는지. 테이블 토큰은 `tableId`가 현재 DB에 존재하는지 확인한다(삭제/재설정된 테이블 토큰 거부).

---

## 4. 서비스 입출력 모델 (계약과 일치)

| 모델 | 필드 | 계약 스키마 |
|---|---|---|
| TableLoginRequest | storeId, tableNumber, password | `TableLoginRequest` |
| AdminLoginRequest | storeId, username, password | `AdminLoginRequest` |
| TokenResponse | accessToken, expiresAt | `TokenResponse` |
| TableTokenResponse | + tableId, tableNumber | `TableTokenResponse` |
| Menu | id, name, price, description, category, imageUrl, displayOrder | `Menu` |
| CategoryMenus | category, menus[] | `CategoryMenus` |
| MenuInput | name, price, description, category, imageUrl | `MenuInput` |
| ReorderRequest | category, orderedIds[] | `ReorderRequest` |
| ApiErrorBody | code, message?, fields?, retryAfterSeconds?, details? | `ApiErrorBody` |

JSON 필드는 camelCase로 직렬화한다 (DB 컬럼은 snake_case).

---

## 5. 도메인 예외

| 예외 | 속성 | 의미 |
|---|---|---|
| `ValidationFailed` | fields: dict[str, str] | 입력 검증 실패 |
| `InvalidCredentials` | - | 로그인 정보 불일치 |
| `Unauthorized` | - | 토큰 없음/만료/위변조/role 불일치 |
| `AccountLocked` | retry_after_seconds: int | 로그인 잠금 |
| `NotFound` | - | 대상 없음 |

(backend-order가 `MenuUnavailable`, `PriceChanged`, `InvalidTransition`, `NoActiveSession`, `DuplicateTable` 등을 추가한다.)
