# 테이블오더 백엔드 (backend-core + backend-order)

FastAPI + SQLite 백엔드입니다.
- backend-core: 인증(관리자/테이블), 메뉴 관리, 프론트엔드 정적 서빙
- backend-order: 테이블 등록, 주문(멱등, 서버 금액 재계산), 테이블 세션/이용 완료(이력 이관), 과거 내역, 실시간 이벤트(SSE)

- 설계: `../aidlc-docs/construction/backend-core/functional-design/`, `../aidlc-docs/construction/backend-order/functional-design/`
- API 계약: `../contracts/openapi.yaml` (테스트가 구현과의 일치를 검증합니다)
- 기술: Python 3.14(개발 확인), FastAPI 0.143, SQLite(`sqlite3` 직접 SQL), bcrypt, PyJWT, tzdata

## 설치 (Windows PowerShell, Docker 미사용)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # 개발/테스트용: pip install -r requirements-dev.txt
```

`requirements.lock.txt` 에 현재 검증된 전체 의존성(전이 의존성 포함) 버전이 있습니다.

## 설정

```powershell
copy .env.example .env
```

`.env` 를 열어 값을 확인하세요. 필수 키: `STORE_ID`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `JWT_SECRET`(32자 이상).
필수값이 없거나 형식이 틀리면 서버가 시작되지 않고 어떤 키가 문제인지만 알려줍니다 (값은 출력하지 않음).

관리자 비밀번호 해시 만들기:

```powershell
python scripts/hash_password.py        # 입력한 비밀번호의 bcrypt 해시 출력
```

출력된 해시를 `.env` 의 `ADMIN_PASSWORD_HASH` 에 **작은따옴표로 감싸** 넣으세요 (`$` 문자 때문).
`.env.example` 의 해시와 `JWT_SECRET` 은 개발용 예시입니다 (비밀번호 `admin1234`). 운영 전에는 반드시 바꾸세요.

전체 설정 키는 `.env.example` 과 `../aidlc-docs/construction/backend-core/functional-design/domain-entities.md` 2절을 참고하세요.

backend-order가 추가한 선택 키:

| 키 | 기본값 | 설명 |
|---|---|---|
| `TIMEZONE` | `Asia/Seoul` | 과거 주문 내역의 날짜(시작일~종료일) 경계에 쓰는 IANA 시간대. DB 시각은 항상 UTC. Windows에는 시간대 데이터가 없어 `tzdata` 패키지를 설치합니다 |
| `SSE_KEEPALIVE_SECONDS` | 15 | 실시간 스트림 `: keep-alive` 주기 |
| `SSE_QUEUE_SIZE` | 100 | 구독자별 이벤트 큐 크기 (넘치면 그 연결만 끊고 클라이언트가 재연결 후 재조회) |

## 실행

```powershell
python scripts/seed.py                 # 개발용 샘플 데이터 (테이블 1~5번 비밀번호 1234, 메뉴 12개와 사진). 여러 번 실행해도 안전
python -m uvicorn app.main:create_app --factory --port 8000 --timeout-graceful-shutdown 5
```

`--timeout-graceful-shutdown` 을 권장합니다: 관리자 화면의 실시간 연결(SSE)이 열려 있으면 uvicorn이 종료 시 그 연결이 닫히기를 기다리므로, 지정한 초 뒤에 강제로 정리하게 합니다 (없으면 Ctrl+C 후 멈춘 것처럼 보일 수 있음).

- API 문서: http://localhost:8000/api/docs
- 프론트엔드: `frontend/dist` 가 있으면 http://localhost:8000 에서 함께 제공됩니다 (`cd ../frontend; npm install; npm run build`). 없으면 API만 제공합니다.
- 시드 초기화: `python scripts/seed.py --reset` (모든 앱 테이블 데이터 삭제 후 다시 입력, 확인 프롬프트. `--yes` 로 생략)
- 시드 메뉴 사진은 Wikimedia Commons 이미지 URL입니다 (`scripts/seed_images.py`에 메뉴별 파일 이름과 출처 안내). 브라우저가 인터넷에서 직접 불러오며, 불러오지 못하면 화면이 메뉴명 첫 글자 대체 이미지를 보여 줍니다. 파일마다 라이선스가 달라 실제 매장 사용 전에는 확인하거나 관리자 화면에서 실제 메뉴 사진 주소로 바꾸세요.
- DB 파일: 기본 `backend/data/table_order.sqlite3` (`DB_PATH` 로 변경)

프론트엔드를 개발 서버로 이 백엔드에 붙이려면: `cd ../frontend; npm run dev:real` (`/api` 를 8000 포트로 프록시).

### 전체 구동 (프론트엔드 + 백엔드, 같은 오리진)

```powershell
cd ../frontend; npm install; npm run build        # VITE_API_MODE=real 로 빌드 (.env.production)
cd ../backend; python scripts/seed.py
python -m uvicorn app.main:create_app --factory --port 8000 --timeout-graceful-shutdown 5
```

- 고객 태블릿: http://localhost:8000/customer/setup (매장 `demo`, 테이블 1, 비밀번호 1234)
- 관리자: http://localhost:8000/admin/login (`demo` / `admin` / `admin1234`, `.env.example` 기준)

## API 요약 (backend-order)

| 구분 | 메서드 경로 | 설명 |
|---|---|---|
| 고객(테이블 토큰) | `POST /api/customer/orders` | 주문 생성. 신규 201, 같은 `clientOrderId` 재전송 200. 서버가 금액을 재계산해 `clientTotal`과 다르면 409 `PRICE_CHANGED`, 판매하지 않는 메뉴는 409 `MENU_UNAVAILABLE` |
| | `GET /api/customer/orders?page&size` | 현재 세션 주문 내역(최신순) |
| 관리자(관리자 토큰) | `GET /api/admin/dashboard[?table=번호]` | 테이블별 요약 (기본 최신 3건, `table` 지정 시 전체) |
| | `GET /api/admin/orders/{orderId}` | 주문 상세 |
| | `PATCH /api/admin/orders/{orderId}/status` | `PENDING -> PREPARING -> COMPLETED` 순차만 (위반 409 `INVALID_TRANSITION`) |
| | `DELETE /api/admin/orders/{orderId}` | 주문 삭제 후 갱신된 테이블 요약 반환 |
| | `GET /api/admin/tables`, `POST /api/admin/tables` | 테이블 목록 / 등록 (번호 1~999, 비밀번호 숫자 4자리, 중복 409) |
| | `POST /api/admin/tables/{tableId}/end-session` | 이용 완료: 주문을 과거 이력으로 이동하고 세션 종료 (활성 세션 없으면 409 `NO_ACTIVE_SESSION`) |
| | `GET /api/admin/tables/{tableId}/history[?from&to]` | 과거 주문 (이용 완료일 기준, `TIMEZONE` 날짜, 시간 역순) |
| | `GET /api/admin/events` | 실시간 이벤트 스트림 (SSE) |

### 실시간 이벤트 (SSE)

- `Authorization: Bearer <관리자 토큰>` 필요. 응답 `text/event-stream`, 프레임은 `event: <type>\ndata: {"type","tableId","payload"}\n\n`.
- 연결 직후 `: connected`, 이후 `SSE_KEEPALIVE_SECONDS` 마다 `: keep-alive` 주석.
- 종류: `order_created {orderId}`, `order_status_changed {orderId,status}`, `order_deleted {orderId}`, `session_ended {archivedOrderCount}`, `menu_changed {}`. 모두 DB 커밋 이후에 발행됩니다.
- 이벤트는 "다시 조회하라"는 신호입니다. 재전송(Last-Event-ID)은 없으며, 연결이 끊기면 재연결 후 대시보드를 다시 조회하세요.
- 사용한 관리자 토큰의 만료 시각이 지나면 서버가 스트림을 닫습니다 (재연결 시 401 -> 로그인 화면).
- 확인 예: `curl.exe -N -H "Authorization: Bearer <토큰>" http://localhost:8000/api/admin/events`

## 테스트

```powershell
pytest                                  # 전체 (단위 + API + 계약 일치 + 통합)
pytest tests/unit                       # 서비스/보안/DB/설정/시드/이벤트 브로커
pytest tests/api                        # HTTP 통합 (TestClient, SSE는 실제 uvicorn 스레드)
pytest tests/contract                   # contracts/openapi.yaml 과 구현 일치 (19개 operation)
pytest tests/integration                # 주문 -> SSE -> 상태 변경 -> 이용 완료 전체 시나리오 (실제 서버)
```

SSE/통합 테스트는 임의의 빈 포트에 uvicorn을 스레드로 띄워 `httpx` 스트림으로 확인합니다 (네트워크 외부 접속 없음, 몇 초 소요).
임시 파일은 `backend/.pytest_tmp` 에 생성됩니다 (git 제외).

## 로그인 잠금 정책

| 대상 | 규칙 |
|---|---|
| 관리자 | 연속 5회 실패 시 15분 잠금 (429, `retryAfterSeconds`). 제출한 사용자명과 무관하게 한 계정으로 집계. 서버 재시작 후에도 유지 |
| 테이블 | 같은 테이블 번호에 연속 10회 실패 시 5분 잠금 |

## 디렉토리 구조

```
backend/
  app/
    main.py            앱 조립, 오류 핸들러, 정적 서빙(SPA 폴백)
    config.py          설정(.env) 로드/검증
    db.py              SQLite 연결, 트랜잭션, 스키마 레지스트리
    schema_core.py     core 스키마(menus, tables, login_attempts)
    schema_order.py    order 스키마(table_sessions, orders, order_items, order_history, order_history_items)
    security.py        bcrypt, JWT
    deps.py            컨테이너, 인증 의존성(require_admin/require_table)
    errors.py          도메인 예외, 오류 본문 형식
    schemas.py         요청/응답 모델, 입력 검증
    events_port.py     이벤트 발행 포트(ServerEvent, EventPublisher)
    events.py          EventBroker(SSE 구독/발행), SSE 프레임/스트림 생성
    services/          auth_service, menu_service, table_service, order_service, order_queries, order_models
    routers/           customer(로그인, 메뉴), customer_orders, admin(로그인, 메뉴 관리), admin_orders(+SSE), admin_tables
  scripts/             seed.py, hash_password.py, load_smoke.py (개발용 가벼운 동시 주문/SSE 확인)
  tests/               unit, api, contract, integration (live.py: 실제 서버 테스트 도구)
```

## 연동 구조 (backend-core <-> backend-order)

| 제공 | 사용 방법 |
|---|---|
| `app.db.register_schema(SchemaModule(...))` | `schema_order.py` 가 `order` 모듈을 등록 (`main.py` 가 core 다음에 import) |
| `Database.connection()` / `transaction()` | 같은 연결·트랜잭션 규칙 (쓰기는 `BEGIN IMMEDIATE`) |
| `require_admin`, `require_table` | 주문/테이블 라우터의 인증 의존성 (`AdminPrincipal.expires_at` 은 SSE 만료 처리용) |
| `MenuService.get_active_menus_by_ids` | 주문 생성 시 가격 재계산, 삭제된 메뉴는 결과에 없음 -> `MENU_UNAVAILABLE` |
| `build_container` | 이벤트는 항상 `EventBroker` 로 가고, `create_app(event_publisher=...)` 를 주면 함께 전달 (테스트용 기록 등). `MenuService` 도 같은 발행기로 `menu_changed` 발행 |
| `app.errors.AppError` 상속 | `MenuUnavailable`, `PriceChanged`, `InvalidTransition`, `NoActiveSession`, `DuplicateTable` |
| `tables` 테이블 | 스키마는 core 소유. 등록 API와 세션은 backend-order (등록 즉시 태블릿 로그인 가능) |

## 알려진 제한 (MVP)

- 단일 프로세스 전제입니다. EventBroker는 프로세스 메모리에 있어 여러 워커로 띄우면 이벤트가 다른 워커의 구독자에게 가지 않습니다.
- 테이블 수정/삭제 API, 과거 내역 페이지네이션, SSE 이벤트 재전송은 없습니다.
- 주문 삭제는 물리 삭제입니다 (서버 로그에 주문/테이블/금액/상태만 남김).
