# Code Generation Plan - frontend (Unit 1)

이 문서는 Unit 1 `frontend`의 Code Generation 단일 기준 문서(single source of truth)입니다. 승인 후 Step 순서대로 생성하며, 각 Step 완료 즉시 체크박스를 `[x]`로 갱신합니다.

## Unit 컨텍스트

- **입력 설계**: `aidlc-docs/construction/frontend/functional-design/` (domain-entities, business-logic-model, business-rules, frontend-components), `aidlc-docs/inception/application-design/` (components, component-methods, unit-of-work*)
- **구현 스토리**: 34개 전체의 UI 부분 (`unit-of-work-story-map.md`). 서버 로직은 mock 구현으로 대체
- **의존성**: 다른 Unit 코드에 의존하지 않음. 유일한 접점은 `contracts/openapi.yaml` (이 Unit에서 작성)
- **소유 산출물**: `contracts/openapi.yaml`, `frontend/` 전체
- **코드 위치**: 워크스페이스 루트 `C:\Users\okpoz\AWS\table_order\` 아래 `contracts/`, `frontend/` (aidlc-docs에는 마크다운 요약만)
- **환경**: Node v24.21.0, npm 11.19.0 확인됨. Docker 없이 로컬 실행
- **기술 선택**: React + TypeScript + Vite, react-router-dom, TanStack Query, CSS Modules, Vitest + React Testing Library, openapi-typescript. 의존성은 `npm install --save-exact`로 정확한 버전을 고정하고 `package-lock.json`을 생성한다
- **SSE 클라이언트**: 별도 라이브러리 없이 `fetch` + `ReadableStream` 파서를 직접 구현 (Authorization 헤더 필요)
- **자동화 친화 규칙**: 모든 상호작용 요소에 안정적인 `data-testid` (`{component}-{element-role}` 형식, 예: `cart-panel-order-button`)

## 실행 중 검증 방침

규칙상 테스트의 본 실행은 Build and Test 단계에서 수행합니다. 다만 생성한 코드가 컴파일되는지 확인하기 위해, 마지막 단계에서 `npm run typecheck`, `npm test`, `npm run build`를 한 번씩 실행해 오류를 수정합니다 (결과는 요약에 기록).

---

## 생성 단계

### Step 1. API 계약 작성 (US 전체의 기준)
- [x] `contracts/openapi.yaml` 생성 (OpenAPI 3.0.3 또는 3.1)
  - 19개 operation: customer 4, admin auth 1, dashboard 1, orders 3 (get/patch status/delete), events(SSE) 1, tables 4 (list/register/end-session/history), menus 5 (list/create/update/delete/reorder)
  - 보안 스킴: `tableBearer`, `adminBearer` (HTTP bearer JWT)
  - 스키마: `domain-entities.md`의 DTO 전체, `ApiError` 본문(코드 enum 포함), `Page` 형태
  - 오류 응답: 401/404/409/422/429/500을 각 operation에 명시
  - 계약 요구: `clientOrderId` 멱등성, 대시보드 `table` 필터 시 전체 주문, 쿼리 파라미터(`page`, `size`, `from`, `to`, `table`)
  - SSE 경로는 `text/event-stream` 응답과 이벤트 규격을 설명으로 문서화
- **스토리**: 전체 (계약 기준)

### Step 2. 프로젝트 스캐폴드
- [x] `frontend/package.json` (scripts: `dev`, `dev:mock`, `build`, `preview`, `typecheck`, `test`, `gen:api`)
- [x] `frontend/tsconfig.json`, `frontend/tsconfig.node.json` (strict 모드)
- [x] `frontend/vite.config.ts` (React 플러그인, `/api` 프록시 -> `http://localhost:8000`, Vitest 설정: jsdom, setup 파일)
- [x] `frontend/index.html`, `frontend/src/vite-env.d.ts`
- [x] `frontend/.env.development` (`VITE_API_MODE=mock`), `frontend/.env.production` (`VITE_API_MODE=real`), `frontend/.env.example`
- [x] `frontend/.gitignore` (node_modules, dist), 루트 `.gitignore`가 없으면 생성
- [x] `npm install --save-exact`로 의존성 설치 및 락 파일 생성
- [x] `frontend/src/test/setup.ts` (jest-dom, localStorage 초기화 등)

### Step 3. API 타입 생성
- [x] `npm run gen:api` 실행 -> `frontend/src/shared/api/generated/schema.d.ts`
- [x] `frontend/src/shared/api/types.ts` (생성 타입의 도메인 별칭: `Menu`, `Order`, `OrderStatus`, `TableSummary`, `ErrorCode` 등)

### Step 4. 공통 유틸과 검증 (shared/utils)
- [x] `formatKRW`, `formatDateTime`, `summarizeItems`, `cartSignature` 구현
- [x] `validators.ts`: 테이블 설정, 관리자 로그인, 테이블 등록, 메뉴 폼, 날짜 범위 검증 (business-rules 1절)
- [x] `errorMessages.ts`: `ErrorCode` -> 한국어 문구 매핑 (business-rules 3~6절)
- [x] 단위 테스트: 유틸/검증/문구 매핑
- **스토리**: US-C2.2, C3.2, E7 외

### Step 5. ApiClient (shared/api)
- [x] `client.ts`: `ApiClient` 인터페이스, 토큰 공급자/401 핸들러 주입, 팩토리 `createApiClient(mode)`
- [x] `errors.ts`: `ApiError` 클래스, 응답 -> 오류 정규화, 네트워크 오류(`NETWORK_ERROR`)
- [x] `realClient.ts`: fetch 기반 구현 (JSON, Authorization 헤더, 타임아웃)
- [x] 단위 테스트: 오류 정규화, 헤더, 401 핸들러 호출 (fetch 모킹)
- **스토리**: US-E1, E3, E9

### Step 6. 공통 UI (shared/ui)
- [x] `Button`, `Modal`, `ConfirmDialog`, `Toast`(Provider + `useToast`), `FormField`, `StatusBadge`, `Spinner`, `EmptyState`, `Card` + CSS Modules
- [x] `frontend/src/styles/global.css` (CSS 변수: 색상, 간격, 최소 터치 대상 44px, 포커스 스타일, `prefers-reduced-motion`)
- [x] 컴포넌트 테스트: Modal 포커스/Esc, ConfirmDialog 처리 중 비활성, FormField 오류 연결, StatusBadge 텍스트
- **스토리**: US-C2.2(44px), A3.2, A3.3(확인 팝업)

### Step 7. 실시간 스트림 (shared/sse)
- [x] `sseParser.ts`: `text/event-stream` 청크 파서 (이벤트 이름, 데이터, 주석/keep-alive 무시)
- [x] `useEventStream.ts`: fetch 스트림 연결, 상태(`connecting|open|reconnecting`), 백오프 재연결 (1,2,4,8,10초), 재연결 콜백, 언마운트 시 중단
- [x] mock 모드에서 `mockEvents` 구독으로 대체하는 어댑터
- [x] 단위 테스트: 파서(분할 청크, 다중 이벤트, keep-alive), 재연결 백오프 계산
- **스토리**: US-A2.2, E6

### Step 8. 가짜 API (mocks)
- [x] `seed.ts`: 샘플 메뉴(카테고리 3~4개, 10개 이상), 테이블 1~5(비밀번호 1234), 관리자 계정(demo/admin/admin1234, 개발용 가짜 값)
- [x] `mockStore.ts`: 인-메모리 상태 + localStorage 영속화(`tableorder.mock.store.v1`) + 탭 간 동기화(BroadcastChannel)
- [x] `mockEvents.ts`: 가짜 SSE 이벤트 발행/구독
- [x] `mockClient.ts`: 19개 operation 구현 (지연 150~400ms, 인증/만료, 잠금 5회/900초, 서버 가격 재계산, `PRICE_CHANGED`/`MENU_UNAVAILABLE`, `clientOrderId` 멱등, 세션 시작/종료, 이력 이관, 순차 상태 전이, 검증, 페이지네이션)
- [x] `mockErrors.ts`: `?mockError=network|server` 강제 오류 훅
- [x] 단위 테스트: 주문 생성/멱등/가격 변경/상태 전이/세션 종료/잠금/검증 (격리된 인스턴스 사용)
- **스토리**: 전체 (서버 동작 대체)

### Step 9. 고객 인증과 장바구니 (customer/auth, customer/cart)
- [x] `customer/auth/storage.ts`, `TableAuthProvider.tsx`, `useTableAuth.ts` (자동 로그인, 재로그인 1회, `needs_setup`/`error` 상태, 5초 자동 재시도)
- [x] `customer/cart/cartReducer.ts`, `storage.ts`, `CartProvider.tsx`, `useCart.ts` (최대 20, 수량 1에서 감소 시 제거, localStorage, `pendingOrder` 정리)
- [x] 단위 테스트: reducer 전 액션, 저장/복원/`tableKey` 불일치, 인증 상태 전이
- **스토리**: US-C1.1, C3.1~C3.3, E3

### Step 10. 고객 화면 (customer/pages, components, hooks)
- [x] hooks: `useMenus`, `useCreateOrder`, `useSessionOrders`
- [x] `TableSetupPage`, `MenuPage`(사이드바 + 그리드 + 장바구니 패널), `CategorySidebar`, `MenuCard`, `CartPanel`, `OrderConfirmModal`, `OrderCompletePage`, `OrderHistoryPage`, `OrderListItem`, `CustomerLayout`
- [x] 주문 확정: `clientOrderId` 재사용, `PRICE_CHANGED`/`MENU_UNAVAILABLE` 처리, 이중 클릭 방지
- [x] 주문 내역: 무한 스크롤(IntersectionObserver) + 5초 폴링(탭이 보일 때) + 실패 안내
- [x] 컴포넌트 테스트: 설정 폼 검증, 메뉴 담기/최대 수량, 장바구니 합계, 주문 성공 흐름(카운트다운), 주문 실패 시 장바구니 유지, 가격 변경 안내, 주문 내역 표시/빈 상태
- **스토리**: US-C1.1, C2.1, C2.2, C3.1~C3.3, C4.1, C4.2, C5.1, C5.2, E1, E2, E3, E6

### Step 11. 관리자 인증과 실시간 (admin/auth, admin/realtime)
- [x] `AdminAuthProvider`, `useAdminAuth`, `storage.ts` (localStorage, 만료 타이머, 401 핸들러, returnTo)
- [x] `AdminRealtimeProvider` (`useEventStream` 연동, 쿼리 무효화, `UnseenOrders`, `markSeen`, `refreshNow`)
- [x] `LoginPage` (잠금 카운트다운), `AdminLayout`, `ConnectionIndicator`
- [x] 테스트: 로그인 성공/실패/잠금, 만료 처리, 이벤트 -> 강조 상태
- **스토리**: US-A1.1, A1.2, A2.2, E4, E9

### Step 12. 관리자 화면 (admin/pages, components, hooks)
- [x] hooks: `useDashboard`, `useOrderDetail`, `useChangeOrderStatus`, `useDeleteOrder`, `useTables`, `useRegisterTable`, `useEndSession`, `useTableHistory`, `useAdminMenus`, `useCreateMenu`, `useUpdateMenu`, `useDeleteMenu`, `useReorderMenus`
- [x] `DashboardPage`, `TableCard`, `OrderRow`, `OrderDetailModal`, `TableHistoryModal`
- [x] `TableManagementPage`, `TableRegisterForm`
- [x] `MenuManagementPage`, `MenuListByCategory`, `MenuForm`
- [x] 컴포넌트 테스트: 대시보드 카드 정렬/미리보기 3건/필터 확장, 상태 변경 버튼(순차)과 `INVALID_TRANSITION` 처리, 주문 삭제 확인 플로우, 이용 완료 확인과 합계 0, 과거 내역 날짜 필터, 메뉴 폼 검증, 위/아래 이동 경계 비활성
- **스토리**: US-A2.1, A2.3~A2.5, A3.1~A3.4, A4.1~A4.4, E5, E7, E8

### Step 13. 앱 셸
- [x] `app/routes.tsx`, `app/providers.tsx`, `app/guards.tsx`(CustomerGuard, AdminGuard), `app/App.tsx`, `src/main.tsx`
- [x] 라우트 맵(business-logic-model 1절), 리다이렉트, 404 처리
- [x] 모드 스위치(`VITE_API_MODE`)에 따른 ApiClient/스트림 선택
- [x] 통합 테스트: 가드 동작(고객 needs_setup 리다이렉트, 관리자 returnTo), mock 모드에서 고객 주문 -> 관리자 대시보드 반영 흐름

### Step 14. 접근성/자동화 속성 점검
- [x] 모든 상호작용 요소에 `data-testid` 존재 및 명명 규칙 준수 점검
- [x] 버튼/입력 최소 44x44px, 오류 `role="alert"`, 폼 라벨 연결 점검

### Step 15. 컴파일/테스트/빌드 스모크 검증
- [x] `npm run typecheck`, `npm test`, `npm run build` 실행 및 오류 수정
- [x] 결과를 코드 요약 문서에 기록 (상세한 테스트 지침은 Build and Test 단계)

### Step 16. 문서화
- [x] `frontend/README.md` (설치, mock/real 모드 실행, 스크립트, 계약 타입 재생성 방법, 디렉토리 구조)
- [x] `aidlc-docs/construction/frontend/code/code-summary.md` (생성 파일 목록, 스토리 매핑, 검증 결과, 백엔드 Unit 인수 사항)

### Step 17. 스토리 추적성 확인
- [x] 34개 스토리의 UI 구현 위치를 요약 문서 표에 기록하고 계획서의 스토리 체크리스트 갱신

---

## 스토리 구현 체크리스트 (Step 완료 시 `[x]`)

고객: [x] US-C1.1 [x] US-C2.1 [x] US-C2.2 [x] US-C3.1 [x] US-C3.2 [x] US-C3.3 [x] US-C4.1 [x] US-C4.2 [x] US-C5.1 [x] US-C5.2

관리자: [x] US-A1.1 [x] US-A1.2 [x] US-A2.1 [x] US-A2.2 [x] US-A2.3 [x] US-A2.4 [x] US-A2.5 [x] US-A3.1 [x] US-A3.2 [x] US-A3.3 [x] US-A3.4 [x] US-A4.1 [x] US-A4.2 [x] US-A4.3 [x] US-A4.4

오류/예외: [x] US-E1 [x] US-E2 [x] US-E3 [x] US-E4 [x] US-E5 [x] US-E6 [x] US-E7 [x] US-E8 [x] US-E9

## 범위 외 (이 Unit에서 하지 않는 것)
- 실제 백엔드 연동 검증 (Unit 3 이후 통합 단계)
- Docker/배포 산출물 (Infrastructure Design 생략, 로컬 실행 전용)
- E2E 브라우저 테스트 (Plan Q6: A에 따라 제외)
- 시드 스크립트 (backend-core)

## 규모 예상
- 17단계, 신규 파일 약 110~140개 (소스, CSS Modules, 테스트 포함), 계약 파일 1개
