# Code Summary - frontend (Unit 1)

애플리케이션 코드는 워크스페이스 루트의 `contracts/`, `frontend/`에 있습니다. 이 문서는 요약만 담습니다.

## 생성 산출물

| 영역 | 경로 | 내용 |
|---|---|---|
| API 계약 | `contracts/openapi.yaml` | 19개 operation, 스키마, 오류 응답, 보안 스킴, 계약 요구사항(멱등, 대시보드 table 필터, SSE 규격) |
| 스캐폴드 | `frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.env.*`, `.gitignore` | 의존성은 `--save-exact`로 고정(`package-lock.json`) |
| 생성 타입 | `frontend/src/shared/api/generated/schema.d.ts` | `npm run gen:api` 결과 |
| 공통 API | `frontend/src/shared/api/` | `ApiClient` 인터페이스, `realClient`, `ApiError`, `authBridge`(토큰 공급 + 401 처리) |
| 공통 SSE | `frontend/src/shared/sse/` | `SseParser`, `useEventStream`(백오프 재연결) |
| 공통 UI | `frontend/src/shared/ui/` | Button, Modal, ConfirmDialog, Toast, FormField, StatusBadge, Spinner, EmptyState, Card, ErrorNotice |
| 유틸 | `frontend/src/shared/utils/` | 포맷터, 검증기, 오류 문구 |
| 가짜 API | `frontend/src/mocks/` | `MockBackend`(서버 규칙 재현), `createMockClient`, 시드 |
| 고객 모듈 | `frontend/src/customer/` | 인증, 장바구니, 메뉴, 주문, 주문 내역, 레이아웃 |
| 관리자 모듈 | `frontend/src/admin/` | 인증, 실시간 Provider, 대시보드, 테이블 관리, 메뉴 관리 |
| 앱 셸 | `frontend/src/app/`, `frontend/src/main.tsx` | 라우트, 가드, Provider 구성, QueryClient |
| 스타일 | `frontend/src/styles/global.css`, 컴포넌트별 `*.module.css` | 디자인 토큰, 터치 대상 44px |
| 문서 | `frontend/README.md` | 실행/스크립트/계약 재생성/백엔드 유의사항 |

파일 수(생성 타입 제외): 소스 67, 테스트 25, CSS 30.

## 설계 대비 차이 (계획서와 다르게 구현한 부분)

| 항목 | 계획 | 실제 | 이유 |
|---|---|---|---|
| 가짜 API 파일 구성 | `mockStore.ts`, `mockEvents.ts`, `mockErrors.ts` | `mockBackend.ts`(상태+이벤트+규칙), `mockClient.ts`(지연, 강제 오류, 인증 래핑), `seed.ts` | 상태와 이벤트가 강하게 결합되어 한 클래스로 두는 편이 단순 |
| ApiClient 팩토리 | `shared/api/client.ts`의 `createApiClient` | `app/ApiClientProvider.tsx` | shared가 mocks를 import하지 않게 의존 방향 유지 |
| 관리자 훅 파일 | 훅마다 파일 | `admin/hooks/useAdminQueries.ts` 한 파일(14개 훅) | 쿼리 키 팩토리를 공유하기 위해 |
| 관리자 토큰 복원 | 마운트 시 | 첫 렌더에서 동기 복원 + 브리지 등록 | 자식 effect가 부모 effect보다 먼저 실행되어 첫 요청에 토큰이 비는 문제 방지 |
| 고객/관리자 Provider 위치 | (미정) | 라우터 아래 전역 | 고객 인증은 자격 증명이 있을 때만 서버 호출, 관리자 PC에는 없음 |

## 통합 테스트로 발견해 고친 문제

- `LoginPage`: 로그인 직후 이미 인증된 상태 분기가 항상 `/admin/dashboard`로 보내 `returnTo`(보호 경로로 접근했던 원래 경로)가 무시됨 -> 원래 경로로 복귀하도록 수정 (US-E9). `app/App.test.tsx`가 이 회귀를 막는다.

## 스토리 구현 위치 (34개)

| 스토리 | 주요 구현 |
|---|---|
| US-C1.1, E3 | `customer/auth/TableAuthProvider.tsx`, `pages/TableSetupPage.tsx` |
| US-C2.1, C2.2 | `customer/pages/MenuPage.tsx`, `components/CategorySidebar.tsx`, `MenuCard.tsx` |
| US-C3.1~C3.3 | `customer/cart/*`, `components/CartPanel.tsx` |
| US-C4.1, C4.2, E1, E2 | `customer/components/OrderConfirmModal.tsx`, `pages/OrderCompletePage.tsx`, `hooks/useCreateOrder.ts` |
| US-C5.1, C5.2, E6(폴링) | `customer/pages/OrderHistoryPage.tsx`, `hooks/useSessionOrders.ts`, `components/OrderListItem.tsx` |
| US-A1.1, A1.2, E4, E9 | `admin/auth/AdminAuthProvider.tsx`, `pages/LoginPage.tsx`, `app/guards.tsx` |
| US-A2.1, A2.5 | `admin/pages/DashboardPage.tsx`, `components/TableCard.tsx` |
| US-A2.2, E6(SSE) | `admin/realtime/AdminRealtimeProvider.tsx`, `shared/sse/useEventStream.ts`, `components/ConnectionIndicator.tsx` |
| US-A2.3, A2.4, E5 | `admin/components/OrderDetailModal.tsx`, `OrderRow.tsx` |
| US-A3.1 | `admin/pages/TableManagementPage.tsx`, `components/TableRegisterForm.tsx` |
| US-A3.2, A3.3, E8 | `OrderDetailModal.tsx`(삭제), `TableCard.tsx`(이용 완료) |
| US-A3.4 | `admin/components/TableHistoryModal.tsx` |
| US-A4.1~A4.4, E7 | `admin/pages/MenuManagementPage.tsx`, `components/MenuForm.tsx`, `MenuListByCategory.tsx` |

## 검증 결과 (생성 직후 스모크 실행)

| 명령 | 결과 |
|---|---|
| `npm run typecheck` | 오류 0 |
| `npm test` | 25개 파일, 166개 테스트 통과 |
| `npm run build` | 성공 (160 모듈, JS 382 kB / gzip 117 kB, CSS 21.7 kB) |

테스트 구성: 공통(유틸/검증/오류 문구/실제 클라이언트/SSE 파서·재연결/UI) + 가짜 백엔드(22) + 고객 모듈(47) + 관리자 모듈(36) + 앱 통합(6).

확인하지 못한 것:
- 브라우저에서의 실제 렌더링/레이아웃 시각 확인 (jsdom 테스트만 수행, 개발 서버는 기동하지 않음)
- 실제 FastAPI 백엔드와의 연동 (Unit 2, 3 이후 통합 단계)
- 실제 SSE 스트림 파싱의 네트워크 동작 (파서와 재연결 로직은 단위 테스트로만 검증)

## 백엔드 Unit에 넘기는 사항

1. 구현 기준은 `contracts/openapi.yaml`. FastAPI가 생성한 OpenAPI와 일치하는지 테스트로 확인할 것.
2. 주문 생성의 `clientOrderId` 멱등성 (같은 ID 재전송 시 200으로 기존 주문 반환).
3. 대시보드 `table` 필터 시 현재 세션 전체 주문 반환, 기본은 테이블별 최신 3건.
4. SSE 이벤트 이름 = `ServerEvent.type`, `data` = `ServerEvent` JSON, `order_created`의 `payload.orderId` 포함, keep-alive 주석 전송.
5. 오류 본문 형식과 코드(`ErrorCode`), `ACCOUNT_LOCKED`의 `retryAfterSeconds`, `PRICE_CHANGED`의 `details.currentPrices`, `MENU_UNAVAILABLE`의 `details.menuIds`.
6. 메뉴 검증 값: 메뉴명 1~50, 설명 0~300, 카테고리 1~30, 가격 100~1,000,000 정수, 이미지 URL 선택(http/https). 테이블 비밀번호는 숫자 4자리, 테이블 번호 1~999.
7. `PUT /api/admin/menus/reorder`를 `/{menuId}`보다 먼저 라우팅.
