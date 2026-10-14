# Application Design (통합 문서)

이 문서는 아래 문서를 요약해 통합한 것입니다. 상세 내용은 각 문서를 참고하세요.

- `components.md`: 컴포넌트 정의와 설계 결정
- `component-methods.md`: 메서드 시그니처, API 경로 표, SSE 규격
- `services.md`: 서비스 책임과 오케스트레이션 흐름
- `component-dependency.md`: 의존성 매트릭스, 통신 패턴, 데이터 흐름

---

## 1. 아키텍처 개요

- **형태**: 단일 FastAPI 프로세스가 REST API, 관리자 SSE, 프론트엔드 정적 파일을 모두 제공한다. DB는 SQLite 파일.
- **백엔드**: Router -> Service 2계층. 서비스가 표준 `sqlite3`로 직접 SQL을 실행한다.
- **프론트엔드**: 하나의 React(TypeScript, Vite) 앱, 라우트로 `/customer/*`와 `/admin/*` 분리. 서버 상태는 TanStack Query, 장바구니/인증은 Context.
- **실시간**: 관리자는 SSE(서버 메모리 Pub/Sub), 고객은 5~10초 폴링.
- **실행**: Docker 없이 로컬 실행. 프론트엔드를 빌드해 FastAPI가 정적 서빙.

## 2. 설계 결정

| 항목 | 결정 |
|---|---|
| 백엔드 계층 | Router -> Service (Repository 없음) |
| DB 접근 | `sqlite3` + 직접 SQL |
| SSE | 메모리 내 EventBroker (asyncio), 커밋 후 발행, 재연결 시 전체 재조회 |
| 프론트엔드 | 단일 앱, 라우트 분리, TanStack Query + Context |
| 테이블 인증 | 로컬 저장 자격 증명으로 시작 시 로그인, 만료 시 재로그인 |
| 관리자 계정 | `.env` (매장ID, 사용자명, bcrypt 해시, JWT 시크릿) |
| API 경로 | `/api/customer/*`, `/api/admin/*` |
| 디렉토리 | 루트에 `backend/`, `frontend/` |

## 3. 컴포넌트 요약

**백엔드 (`backend/app/`)**: Config, Database, Security, Auth Deps, EventBroker, AuthService, MenuService, TableService, OrderService, Routers(customer_auth, customer_menu, customer_orders, admin_auth, admin_orders, admin_tables, admin_menus), App Entry(main)

**프론트엔드 (`frontend/src/`)**: Shared(ApiClient, useEventStream, 공통 UI), Customer(TableAuthProvider, CartProvider, Setup/Menu/Cart/Confirm/Result/History 페이지), Admin(AdminAuthProvider, Login, Dashboard, TableCard/OrderDetailModal, TableManagement, TableHistoryModal, MenuManagementPage), App Shell

## 4. 서비스 요약

| 서비스 | 핵심 책임 |
|---|---|
| AuthService | 관리자/테이블 로그인, 로그인 잠금(5회/15분), 토큰 발급 |
| MenuService | 메뉴 CRUD, 노출 순서, 입력 검증 |
| TableService | 테이블 등록, 세션 시작/종료, 이력 이관과 조회 |
| OrderService | 주문 생성(서버 금액 재계산), 상태 순차 전이, 삭제, 대시보드 요약, 이벤트 발행 |

## 5. 의존 관계 요약

Router -> Service -> (Database, Security, EventBroker, Config). OrderService만 MenuService와 TableService를 사용한다. 순환 의존 없음. 프론트엔드 Customer와 Admin 모듈은 서로 참조하지 않고 Shared만 사용한다.

## 6. 스토리 -> 컴포넌트 매핑 (설계 완전성 검증)

| 스토리 | 백엔드 | 프론트엔드 |
|---|---|---|
| US-C1.1 자동 로그인 | AuthService.login_table, customer_auth | TableAuthProvider |
| US-C2.1, C2.2 메뉴 | MenuService.list_menus_grouped, customer_menu | MenuPage, useMenus |
| US-C3.1~C3.3 장바구니 | (서버 없음, 주문 시에만 전송) | CartProvider, CartPanel |
| US-C4.1, C4.2 주문 | OrderService.create_order, customer_orders | OrderConfirmView, OrderResultView, useCreateOrder |
| US-C5.1, C5.2 내역/상태 | OrderService.list_session_orders | OrderHistoryPage, useSessionOrders(폴링) |
| US-A1.1, A1.2 관리자 인증 | AuthService.login_admin, Security, Deps | AdminAuthProvider, LoginPage |
| US-A2.1~A2.3, A2.5 대시보드 | OrderService.dashboard_snapshot/get_order | DashboardPage, TableCard, OrderDetailModal |
| US-A2.2 실시간 | EventBroker, admin_orders SSE | useEventStream, useDashboard |
| US-A2.4 상태 변경 | OrderService.change_status | useChangeOrderStatus |
| US-A3.1 테이블 설정 | TableService.register_table, AuthService.login_table | TableManagement, TableSetupPage |
| US-A3.2 주문 삭제 | OrderService.delete_order | OrderDetailModal(확인 팝업), useDeleteOrder |
| US-A3.3 이용 완료 | TableService.get_or_start_session/end_session | TableManagement, useEndSession |
| US-A3.4 과거 내역 | TableService.list_history | TableHistoryModal, useTableHistory |
| US-A4.1~A4.4 메뉴 관리 | MenuService, admin_menus | MenuManagementPage |
| US-E1, E2 주문 오류 | OrderService.create_order (검증/오류), 도메인 오류 변환 | useCreateOrder 오류 처리, 장바구니 유지 |
| US-E3 테이블 로그인 실패 | AuthService.login_table | TableAuthProvider(needs_setup) |
| US-E4 로그인 잠금 | AuthService.login_admin (429) | LoginPage 잠금 안내 |
| US-E5 잘못된 전이 | OrderService.change_status (409) | 오류 피드백 |
| US-E6 연결 복구 | EventBroker, SSE keep-alive | useEventStream 재연결, 폴링 재시도 |
| US-E7 입력 검증 | MenuService (422 필드 오류) | 메뉴 폼 오류 표시 |
| US-E8 삭제/완료 실패 | 트랜잭션, 409/404 변환 | 실패 피드백 |
| US-E9 세션 만료 | Deps(401) | ApiClient 401 처리, 로그인 화면 이동 |

모든 스토리(34개)가 최소 하나의 백엔드 또는 프론트엔드 컴포넌트에 매핑되었다.

## 7. Functional Design으로 넘기는 항목

- SQLite 스키마(테이블, 컬럼, 인덱스, 제약)와 OrderHistory 이관 방식(복사 vs 플래그)
- 주문 상태 전이 표, 경합 처리, 주문 번호 생성 규칙
- 로그인 실패 기록 저장 방식(SQLite 테이블)과 `client_key` 정의
- 가격 범위, 필수 필드 등 검증 규칙의 구체 값
- 장바구니 localStorage 키/스키마, 테이블 자격 증명 저장 형식
- 대시보드 "최신 주문 n개"의 n 값, 페이지 크기, 폴링 주기(5~10초 중 확정)
- SSE 클라이언트 구현 방식(fetch 기반 라이브러리 또는 직접 구현)
