# Frontend Components - frontend (Unit 1)

컴포넌트 계층, props/state, 상호작용, API 연동 지점을 정의합니다. 스타일은 CSS Modules(컴포넌트별 `*.module.css`), 모든 터치 대상은 최소 44x44px입니다.

## 1. 디렉토리 구조 (설계 수준)

```
frontend/src/
  app/            App.tsx, routes.tsx, providers.tsx, guards (CustomerGuard, AdminGuard)
  shared/
    api/          client.ts (ApiClient 인터페이스), realClient.ts, errors.ts, generated/ (openapi-typescript 출력)
    sse/          useEventStream.ts
    ui/           Button, Modal, ConfirmDialog, Toast, Card, StatusBadge, Spinner, EmptyState, FormField
    utils/        formatKRW, formatDateTime, summarizeItems, validators
  customer/
    auth/         TableAuthProvider, useTableAuth, storage
    cart/         CartProvider, useCart, cartReducer, storage
    pages/        TableSetupPage, MenuPage, OrderHistoryPage, OrderCompletePage
    components/   CategorySidebar, MenuCard, CartPanel, OrderConfirmModal, OrderListItem
    hooks/        useMenus, useCreateOrder, useSessionOrders
  admin/
    auth/         AdminAuthProvider, useAdminAuth, storage
    realtime/     AdminRealtimeProvider (SSE 연결, 상태, UnseenOrders)
    pages/        LoginPage, DashboardPage, TableManagementPage, MenuManagementPage
    components/   AdminLayout, ConnectionIndicator, TableCard, OrderRow, OrderDetailModal,
                  TableHistoryModal, TableRegisterForm, MenuForm, MenuListByCategory
    hooks/        useDashboard, useOrderDetail, useChangeOrderStatus, useDeleteOrder,
                  useTables, useRegisterTable, useEndSession, useTableHistory,
                  useAdminMenus, useCreateMenu, useUpdateMenu, useDeleteMenu, useReorderMenus
  mocks/          mockClient.ts, mockStore.ts, mockEvents.ts, seed.ts
```

---

## 2. 공통 (shared)

### ApiClient (인터페이스)
- 역할: 모든 HTTP 호출의 단일 진입점. mock/real 구현을 환경변수로 교체.
- 메서드(요약): 계약의 operation별 함수 (`customerLogin`, `getCustomerMenus`, `createOrder`, `listSessionOrders`, `adminLogin`, `getDashboard`, `getOrder`, `changeOrderStatus`, `deleteOrder`, `listTables`, `registerTable`, `endSession`, `getTableHistory`, `listAdminMenus`, `createMenu`, `updateMenu`, `deleteMenu`, `reorderMenus`, `openEventStream`).
- 동작: 인증 토큰 공급자를 주입받아 헤더에 부착, 오류를 `ApiError`로 정규화, `UNAUTHORIZED` 시 등록된 핸들러(고객: 재로그인, 관리자: 로그아웃) 호출.

### useEventStream
- props: `{ enabled: boolean; getToken(): string | null; onEvent(e: ServerEvent): void; onReconnected(): void }`
- state: `status: StreamStatus`
- 동작: fetch 기반 SSE(Authorization 헤더), 이벤트 파싱, 끊김 시 1,2,4,8,10초 백오프 재연결, 재연결 성공 시 `onReconnected`. mock 모드에서는 `mockEvents`를 구독.

### UI 컴포넌트

| 컴포넌트 | props | 비고 |
|---|---|---|
| `Button` | `variant`, `disabled`, `loading`, `onClick`, `children` | 최소 44x44px, loading 중 클릭 무시 |
| `Modal` | `open`, `title`, `onClose`, `children` | 포커스 트랩, Esc 닫기, `role="dialog"` |
| `ConfirmDialog` | `open`, `message`, `confirmLabel`, `onConfirm`, `onCancel`, `pending` | 처리 중 확인 비활성 |
| `Toast` (Provider + `useToast`) | `show({type, message})` | 3초(오류 5초) |
| `StatusBadge` | `status: OrderStatus` | 텍스트 + 색 |
| `FormField` | `label`, `error`, `children` | `aria-describedby`로 오류 연결, 오류에 `role="alert"` |
| `EmptyState`, `Spinner`, `Card` | - | - |

### 유틸
`formatKRW(n)`, `formatDateTime(iso)`, `summarizeItems(items)`(첫 메뉴 + 외 N건), `validators`(business-rules의 검증 함수 모음, 순수 함수)

---

## 3. 고객 모듈

### TableAuthProvider
- state: `TableAuthState`, 메모리 토큰
- 동작: 시작 시 자격 증명 읽기 -> 로그인. `setup(storeId, tableNumber, password)`, `retry()`, `getToken()`, `relogin()`.
- API: `POST /api/customer/auth/login`

### CartProvider
- state: `Cart`, 파생 `totalAmount`, `totalCount`
- 액션: `add`, `increase`, `decrease`, `remove`, `clear`, `refreshPrices`, `removeMany`
- 부수 효과: localStorage 동기화(`tableorder.cart.v1`), 변경 시 `pendingOrder` 정리

### TableSetupPage (`/customer/setup`)
- state: 폼 값, 필드별 오류, 제출 중, 서버 오류
- 상호작용: 제출 -> 검증 -> `setup()` -> 성공 시 메뉴로 이동
- 스토리: US-C1.1, US-A3.1(태블릿 측), US-E3

### MenuPage (`/customer/menu`)
- 구성: `CustomerLayout`(상단: 테이블 번호 표시 + "메뉴"/"주문 내역" 탭) 안에 `CategorySidebar` / 메뉴 그리드 / `CartPanel`
- state: 선택된 카테고리(scroll-spy), 주문 확인 모달 열림 여부
- API: `GET /api/customer/menus` (`useMenus`)
- 스토리: US-C2.1, C2.2

### CategorySidebar
- props: `categories: string[]`, `activeCategory`, `onSelect(category)`
- 세로 버튼 목록, 활성 항목 강조, 각 버튼 44px 이상

### MenuCard
- props: `menu: Menu`, `onAdd(menu)`, `atMax: boolean`
- 표시: 이미지(실패 시 대체), 메뉴명, 설명, 가격, "담기" 버튼 (`atMax`면 비활성 + 안내)

### CartPanel
- props: 없음 (`useCart` 사용), `onOrderClick()`
- 표시: 항목 목록(메뉴명, 단가, 수량 -/+, 소계, 삭제), 합계, "비우기", "주문하기"(빈 장바구니면 비활성)
- 스토리: US-C3.1~C3.3

### OrderConfirmModal
- props: `open`, `onClose`, `onSuccess(orderNumber)`
- state: `phase: 'confirm' | 'submitting' | 'error'`, `error: ApiError | null`
- 동작: 확정 시 `useCreateOrder`. 오류 코드별 UI는 business-rules 3절. `PRICE_CHANGED`/`MENU_UNAVAILABLE`에서 `CartProvider`의 `refreshPrices`/`removeMany` 호출
- API: `POST /api/customer/orders`
- 스토리: US-C4.1, E1, E2

### OrderCompletePage (`/customer/order-complete`)
- 입력: 라우터 state의 `orderNumber`
- state: `secondsLeft` (5 -> 0)
- 동작: 1초마다 감소, 0이 되면 `/customer/menu`로 이동, "바로 메뉴로 이동" 버튼. state가 없으면 즉시 메뉴로
- 스토리: US-C4.2

### OrderHistoryPage (`/customer/orders`)
- state: `useInfiniteQuery` 결과, 폴링 실패 안내 여부
- 동작: 5초 폴링(탭이 보일 때), IntersectionObserver sentinel로 다음 페이지
- API: `GET /api/customer/orders?page&size=10` (`useSessionOrders`)
- 하위: `OrderListItem`(props: `order: Order`) - 주문 번호, 시각, 메뉴/수량, 금액, `StatusBadge`
- 스토리: US-C5.1, C5.2, E6(폴링 복구)

---

## 4. 관리자 모듈

### AdminAuthProvider
- state: `AdminAuthState`
- 동작: 저장 토큰 복원, `login(...)`, `logout()`, 만료 타이머, `getToken()`, ApiClient의 `UNAUTHORIZED` 핸들러 등록
- API: `POST /api/admin/auth/login`

### LoginPage (`/admin/login`)
- state: 폼 값, 오류, 제출 중, `lockedUntil`(카운트다운)
- 동작: 제출 -> 로그인. 잠금 시 남은 시간 표시와 버튼 비활성
- 스토리: US-A1.1, A1.2, E4, E9

### AdminLayout
- 구성: 상단 내비(대시보드 / 테이블 관리 / 메뉴 관리), `ConnectionIndicator`, 새로고침 버튼, 로그아웃
- `AdminRealtimeProvider`를 감싸 SSE를 관리자 영역 전체에서 한 번만 연결

### AdminRealtimeProvider
- state: `status: StreamStatus`, `unseen: UnseenOrders`
- 동작: `useEventStream`으로 연결. 이벤트 -> 쿼리 무효화, `order_created`면 `unseen` 갱신. `markSeen(tableId)` 제공
- 제공: `{ status, unseen, markSeen, refreshNow() }`

### DashboardPage (`/admin/dashboard`)
- state: `tableFilter: number | null`
- API: `GET /api/admin/dashboard?table=` (`useDashboard`)
- 구성: 필터 드롭다운, `TableCard` 그리드(번호 오름차순)
- 스토리: US-A2.1, A2.2, A2.5

### TableCard
- props: `summary: TableSummary`, `highlighted: boolean`, `expanded: boolean`, `onViewAll()`, `onOpenOrder(orderId)`, `onEndSession()`, `onOpenHistory()`
- 표시: 테이블 번호, 총 주문액, 주문 개수, 주문 목록(`OrderRow`; 기본 3건, `expanded`면 전체), 버튼: 전체 보기, 과거 내역, 이용 완료(세션 없으면 비활성)
- 강조: `highlighted`면 배경색 + 펄스 애니메이션 (`prefers-reduced-motion`이면 애니메이션 없이 색/테두리만)
- 클릭: 헤더 또는 `OrderRow` 클릭 -> `markSeen(tableId)`

### OrderRow
- props: `order: Order`, `onClick()`
- 표시: 주문 번호, 시각, 메뉴 요약, 금액, `StatusBadge`

### OrderDetailModal
- props: `orderId: number | null`, `onClose()`
- API: `GET /api/admin/orders/{id}`, `PATCH .../status`, `DELETE ...`
- 표시: 테이블 번호, 주문 번호, 시각, 전체 항목(메뉴/수량/단가/소계), 총 금액, 상태, "다음 단계" 버튼, "삭제" 버튼 -> `ConfirmDialog`
- 스토리: US-A2.3, A2.4, A3.2, E5, E8

### TableHistoryModal
- props: `table: {id, tableNumber} | null`, `onClose()`
- state: `from`, `to`, 필터 오류
- API: `GET /api/admin/tables/{id}/history?from&to`
- 표시: 시간 역순 목록(주문 번호, 시각, 메뉴 목록, 총 금액, 이용 완료 시각), "닫기"
- 스토리: US-A3.4

### TableManagementPage (`/admin/tables`)
- 구성: `TableRegisterForm`(테이블 번호, 비밀번호 4자리) + 테이블 목록(번호, 이용 중/비어 있음, 이용 완료 버튼, 과거 내역 버튼)
- API: `GET/POST /api/admin/tables`, `POST /api/admin/tables/{id}/end-session`
- 스토리: US-A3.1, A3.3, E8

### MenuManagementPage (`/admin/menus`)
- 구성: "메뉴 등록" 버튼, `MenuListByCategory`(카테고리 섹션, 행: 이미지 썸네일, 메뉴명, 가격, 수정/삭제/위로/아래로), `MenuForm` 모달
- `MenuForm` props: `initial?: Menu`, `categories: string[]`, `onSubmit(MenuInput)`, `onClose()`; state: 필드값, 필드별 오류, 제출 중
- API: `GET/POST /api/admin/menus`, `PUT/DELETE /api/admin/menus/{id}`, `PUT /api/admin/menus/reorder`
- 스토리: US-A4.1~A4.4, E7

---

## 5. API 연동 표

| 컴포넌트/훅 | 엔드포인트 | 인증 |
|---|---|---|
| TableAuthProvider | `POST /api/customer/auth/login` | 없음 |
| useMenus | `GET /api/customer/menus` | table |
| useCreateOrder | `POST /api/customer/orders` | table |
| useSessionOrders | `GET /api/customer/orders` | table |
| AdminAuthProvider | `POST /api/admin/auth/login` | 없음 |
| useDashboard | `GET /api/admin/dashboard` | admin |
| useOrderDetail | `GET /api/admin/orders/{id}` | admin |
| useChangeOrderStatus | `PATCH /api/admin/orders/{id}/status` | admin |
| useDeleteOrder | `DELETE /api/admin/orders/{id}` | admin |
| AdminRealtimeProvider | `GET /api/admin/events` (SSE) | admin |
| useTables / useRegisterTable | `GET/POST /api/admin/tables` | admin |
| useEndSession | `POST /api/admin/tables/{id}/end-session` | admin |
| useTableHistory | `GET /api/admin/tables/{id}/history` | admin |
| useAdminMenus / useCreateMenu / useUpdateMenu / useDeleteMenu / useReorderMenus | `/api/admin/menus*` | admin |

모두 19개 경로 (component-methods.md의 API 표와 동일).

---

## 6. 스토리 커버리지 검증

| 스토리 | 설계 반영 위치 |
|---|---|
| US-C1.1 | TableAuthProvider, TableSetupPage, business-logic-model 2.1 |
| US-C2.1 | MenuPage, CategorySidebar (2.2) |
| US-C2.2 | MenuCard, 표시 규칙(이미지 대체, 44px) |
| US-C3.1~C3.3 | CartProvider, CartPanel, 장바구니 규칙(business-rules 2) |
| US-C4.1 | OrderConfirmModal, 주문 확정 규칙 1~3 |
| US-C4.2 | OrderCompletePage (5초 카운트다운 + 바로 이동) |
| US-C5.1 | OrderHistoryPage, OrderListItem, 무한 스크롤 |
| US-C5.2 | 5초 폴링 규칙 |
| US-A1.1, A1.2 | AdminAuthProvider, LoginPage, 인증 규칙(localStorage + 만료 타이머) |
| US-A2.1 | DashboardPage, TableCard |
| US-A2.2 | AdminRealtimeProvider, useEventStream, 신규 주문 강조 |
| US-A2.3 | OrderDetailModal |
| US-A2.4 | 상태 변경 규칙 ("다음 단계" 버튼) |
| US-A2.5 | 테이블 필터 드롭다운, `expanded` 카드 |
| US-A3.1 | TableManagementPage, TableRegisterForm, TableSetupPage(태블릿) |
| US-A3.2 | OrderDetailModal 삭제 + ConfirmDialog |
| US-A3.3 | TableCard/TableManagementPage 이용 완료 + ConfirmDialog |
| US-A3.4 | TableHistoryModal |
| US-A4.1~A4.4 | MenuManagementPage, MenuForm, 위/아래 이동 |
| US-E1 | OrderConfirmModal 오류 처리, `clientOrderId` 재사용 |
| US-E2 | `PRICE_CHANGED`/`MENU_UNAVAILABLE` UI |
| US-E3 | TableAuthProvider `needs_setup`, 설정 화면 오류 |
| US-E4 | LoginPage 잠금 카운트다운 |
| US-E5 | `INVALID_TRANSITION` 처리 |
| US-E6 | useEventStream 재연결, 폴링 실패 안내 |
| US-E7 | MenuForm 필드별 오류, 검증 규칙 |
| US-E8 | ConfirmDialog 실패 피드백, `NO_ACTIVE_SESSION`/`NOT_FOUND` 처리 |
| US-E9 | AdminAuthProvider `UNAUTHORIZED` 처리, returnTo |

34개 스토리가 모두 설계에 반영되었다.
