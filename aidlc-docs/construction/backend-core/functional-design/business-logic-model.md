# Business Logic Model - backend-core (Unit 2)

서비스 흐름과 트랜잭션 경계를 정의한다. 규칙의 구체 값은 `business-rules.md`, 스키마는 `domain-entities.md`를 참고한다.

## 1. 구성 요소와 책임 (Application Design 기준)

| 컴포넌트 | 책임 |
|---|---|
| Settings (`config.py`) | `.env` 로드/검증 |
| Database (`db.py`) | 연결 팩토리, 트랜잭션 헬퍼, 스키마 초기화(모듈 등록) |
| Security (`security.py`) | bcrypt 해시/검증, JWT 발급/검증 |
| Auth Deps (`deps.py`) | `require_admin`, `require_table` |
| AuthService | 관리자/테이블 로그인, 잠금 |
| MenuService | 메뉴 조회/CRUD/순서, 다른 Unit용 조회 |
| Routers | `customer_auth`, `customer_menu`, `admin_auth`, `admin_menus` |
| App Entry (`main.py`) | 조립, 오류 핸들러, 정적 서빙 |
| `scripts/seed.py`, `scripts/hash_password.py` | 시드, 관리자 비밀번호 해시 생성 |

의존: Router -> Service -> (Database, Security, Settings). 서비스는 HTTP를 모른다. 시각은 주입 가능한 `clock()`을 사용한다(테스트용).

## 2. 시작 흐름

```
main 앱 생성 (lifespan)
  -> Settings 로드/검증 (실패 시 종료)
  -> Database 초기화: 디렉토리 생성, 연결 옵션 확인
  -> 스키마 초기화: schema_registry의 모듈들을 순서대로 적용 ('core' v1)
  -> 서비스 인스턴스 구성 (MenuService에는 이벤트 발행기: 기본 no-op)
  -> 라우터/오류 핸들러 등록
  -> 정적 서빙 등록 (FRONTEND_DIST 존재 시)
```

스키마 레지스트리: `register_schema(module: str, version: int, apply: Callable[[Connection], None])`. backend-order가 같은 방식으로 `order` 모듈을 등록한다. 적용 순서는 등록 순서.

## 3. 관리자 로그인 (US-A1.1, A1.2, E4)

```
POST /api/admin/auth/login
  -> 요청 본문 검증 (ValidationFailed -> 422)
  -> AuthService.login_admin(store_id, username, password)
       BEGIN IMMEDIATE
         row = login_attempts[admin/account]
         if row.locked_until > now: ROLLBACK -> AccountLocked(ceil(locked_until-now))
         if row.locked_until <= now: row 초기화
         ok = (store_id == settings.store_id) & (username == settings.admin_username)
              & verify_password(password, settings.admin_password_hash)   # 항상 해시 검증 수행
         if not ok:
             failure_count += 1
             if failure_count >= 5: locked_until = now+15m; failure_count = 0; COMMIT -> AccountLocked(900)
             else: COMMIT -> InvalidCredentials
         else: row 삭제/초기화; COMMIT
       token = create_token(role=admin, ...)
  <- 200 { accessToken, expiresAt }
```

주의: 실패/잠금 기록은 오류를 던지기 전에 반드시 커밋한다 (오류 때문에 롤백되어 횟수가 사라지지 않도록, 예외 전에 커밋 후 던진다).

## 4. 테이블 로그인 (US-C1.1, E3)

```
POST /api/customer/auth/login
  -> 검증 (422)
  -> AuthService.login_table(store_id, table_number, password)
       if store_id != settings.store_id: InvalidCredentials
       table = SELECT ... WHERE table_number=?
       if not table: verify_password(password, DUMMY_HASH); InvalidCredentials
       BEGIN IMMEDIATE
         row = login_attempts[table/<번호>]
         if 잠금 중: AccountLocked
         if verify_password(password, table.password_hash):
             row 초기화; COMMIT; 토큰 발급
         else:
             failure_count += 1; 10 이상이면 locked_until=now+5m, failure_count=0
             COMMIT -> (잠금이면 AccountLocked(300), 아니면 InvalidCredentials)
  <- 200 { accessToken, expiresAt, tableId, tableNumber }
```

## 5. 토큰 검증 (US-A1.2, E9)

```
요청 -> Authorization 헤더 파싱
  -> Security.decode_token: 서명/exp 검증 (실패 -> Unauthorized)
  -> role, storeId 확인 (불일치 -> Unauthorized)
  -> require_table: 테이블 존재 확인 (없으면 Unauthorized)
  -> 라우터에 Principal(AdminPrincipal | TablePrincipal) 전달
```
JWT에는 서버 상태가 없으므로 로그아웃 서버 처리는 없다 (클라이언트가 토큰 삭제). 16시간 후 `exp`로 만료.

## 6. 메뉴 조회 (US-C2.1, C2.2, A4.1)

```
GET /api/customer/menus | GET /api/admin/menus
  -> MenuService.list_grouped()
       SELECT ... FROM menus WHERE deleted_at IS NULL ORDER BY category_order, display_order
       categories 순서대로 그룹화 -> CategoryMenus[]
  <- 200
```

## 7. 메뉴 등록 (US-A4.2, E7)

```
POST /api/admin/menus
  -> 검증 (모든 필드 오류 수집)
  -> MenuService.create(input)
       BEGIN IMMEDIATE
         중복 이름 검사 (활성, 같은 category)
         category_order / display_order 결정 (business-rules 3.2)
         INSERT
       COMMIT
       publish(menu_changed)    # 커밋 이후
  <- 201 Menu
```
중복 검사와 삽입 사이의 경쟁은 `BEGIN IMMEDIATE`와 부분 유니크 인덱스가 막는다. 유니크 위반(`IntegrityError`)이 나면 같은 중복 이름 422로 변환한다.

## 8. 메뉴 수정 / 삭제 / 순서 변경 (US-A4.3, A4.4, E7)

수정:
```
PUT /api/admin/menus/{id}
  -> 검증
  -> MenuService.update(id, input)
       BEGIN IMMEDIATE
         m = SELECT ... WHERE id=? AND deleted_at IS NULL  (없으면 NotFound)
         중복 이름 검사 (id 제외)
         if category 변경: 새 카테고리 order 결정 -> 이전 카테고리 재번호
         UPDATE
       COMMIT; publish(menu_changed)
  <- 200 Menu
```
삭제:
```
DELETE /api/admin/menus/{id}
  -> MenuService.delete(id)
       BEGIN IMMEDIATE; m 조회(활성만, 없으면 NotFound); UPDATE deleted_at; 같은 카테고리 재번호; COMMIT
       publish(menu_changed)
  <- 204
```
순서 변경:
```
PUT /api/admin/menus/reorder   { category, orderedIds }
  -> MenuService.reorder(category, ordered_ids)
       BEGIN IMMEDIATE; 활성 메뉴 ID 집합 조회(없으면 NotFound); 집합 일치 검증(422); display_order 갱신; COMMIT
       publish(menu_changed)
  <- 204
```
라우팅 주의: `/api/admin/menus/reorder`를 `/api/admin/menus/{menu_id}`보다 먼저 등록한다.

## 9. 다른 Unit과의 접점 (backend-order용)

| 제공 | 사용자 | 설명 |
|---|---|---|
| `Database.get_connection()/transaction()` | TableService, OrderService | 같은 연결/트랜잭션 규칙 |
| `register_schema(...)` | backend-order | 주문 관련 테이블 추가 |
| `Security`, `require_admin/require_table` | 주문/테이블 라우터 | 인증 의존성 재사용 |
| `MenuService.get_active_menus_by_ids` | OrderService | 삭제된 메뉴 제외, 현재 가격 제공 |
| `MenuService(event_publisher=...)` 주입 | App Entry(backend-order에서 연결) | `menu_changed` 발행 |
| `tables` 테이블 | TableService | 등록 API는 backend-order |
| 도메인 예외 기반 클래스, 오류 핸들러 | backend-order | 새 예외를 같은 핸들러 체계에 추가 |

## 10. 계약 검증 대상 (이 Unit)

| operation | 경로 | 인증 | 응답 |
|---|---|---|---|
| customerLogin | POST /api/customer/auth/login | 없음 | 200, 401, 422, 429, 500 |
| getCustomerMenus | GET /api/customer/menus | table | 200, 401, 500 |
| adminLogin | POST /api/admin/auth/login | 없음 | 200, 401, 422, 429, 500 |
| listAdminMenus | GET /api/admin/menus | admin | 200, 401, 500 |
| createMenu | POST /api/admin/menus | admin | 201, 401, 422, 500 |
| reorderMenus | PUT /api/admin/menus/reorder | admin | 204, 401, 404, 422, 500 |
| updateMenu | PUT /api/admin/menus/{menuId} | admin | 200, 401, 404, 422, 500 |
| deleteMenu | DELETE /api/admin/menus/{menuId} | admin | 204, 401, 404, 500 |

(8개 operation. 계약 검증 테스트는 이 경로들의 존재, 메서드, 응답 상태 코드, 스키마 필드가 `contracts/openapi.yaml`과 일치하는지 확인한다.)

## 11. 스토리 반영 확인 (13개)

| 스토리 | 반영 위치 |
|---|---|
| US-C1.1 자동 로그인 | 4절 테이블 로그인, 2.2 규칙 |
| US-C2.1, C2.2 메뉴 조회 | 6절, business-rules 3.1 |
| US-A1.1 관리자 로그인 | 3절, 2.1 |
| US-A1.2 16시간 세션 | 토큰 `exp`, 5절 |
| US-A4.1 메뉴 목록 | 6절 |
| US-A4.2 메뉴 등록 | 7절, 3.2 |
| US-A4.3 수정/삭제 | 8절, 3.3, 3.4 |
| US-A4.4 순서 조정 | 8절, 3.5 |
| US-E3 테이블 로그인 실패 | 4절 (401/429), 오류 매핑 |
| US-E4 관리자 잠금 | 3절, 2.1 |
| US-E7 메뉴 검증 | 1절 규칙, 7절 |
| US-E9 세션 만료 | 5절 (401 UNAUTHORIZED) |

13개 모두 반영됨.
