# 테이블오더 프론트엔드

고객용(테이블 태블릿)과 관리자용(매장 운영자) 화면을 하나의 React 앱으로 제공합니다.

- 기술: React 19, TypeScript, Vite, react-router-dom, TanStack Query, CSS Modules, Vitest + React Testing Library
- 설계 문서: `../aidlc-docs/construction/frontend/functional-design/`
- API 계약: `../contracts/openapi.yaml`

## 실행

사전 준비: Node.js 20.19 이상 (개발 확인: Node 24, npm 11)

```bash
cd frontend
npm install
```

### 1. mock 모드 (백엔드 없이, 기본)

```bash
npm run dev
```

브라우저에서 `http://localhost:5173` 을 엽니다. 인-메모리 가짜 API가 동작하며 데이터는 브라우저 localStorage(`tableorder.mock.store.v1`)에 저장되어 같은 브라우저의 여러 탭이 공유합니다. (탭 간 실시간 이벤트는 BroadcastChannel)

개발용 가짜 데이터:

| 항목 | 값 |
|---|---|
| 매장 식별자 | `demo` |
| 관리자 | 사용자명 `admin`, 비밀번호 `admin1234` |
| 테이블 | 1~5번, 비밀번호 `1234` |

시나리오 예시:
1. 탭 A: `/customer` -> 초기 설정(demo / 1 / 1234) -> 메뉴 담기 -> 주문
2. 탭 B: `/admin` -> 로그인 -> 대시보드에서 주문이 즉시 나타나고 강조되는지 확인 -> 상태 변경 -> 이용 완료

데이터 초기화: 브라우저 개발자도구에서 localStorage의 `tableorder.*` 키를 삭제합니다.

오류 상황 재현: 주소 뒤에 `?mockError=network` 또는 `?mockError=server` 를 붙이면 모든 API 호출이 해당 오류로 실패합니다.

### 2. real 모드 (실제 백엔드 연동)

```bash
npm run dev:real     # /api 요청을 http://localhost:8000 으로 프록시
```

실제 배포 형태(FastAPI가 정적 서빙)에서는 `npm run build` 후 `dist/`를 백엔드가 제공합니다. 프로덕션 빌드는 `VITE_API_MODE=real` 입니다 (`.env.production`).

## 스크립트

| 명령 | 설명 |
|---|---|
| `npm run dev` | 개발 서버 (mock 모드) |
| `npm run dev:real` | 개발 서버 (real 모드) |
| `npm run build` | 타입 검사 + 프로덕션 빌드 (`dist/`) |
| `npm run typecheck` | 타입 검사만 |
| `npm test` | 전체 테스트 1회 실행 (Vitest) |
| `npm run test:watch` | 테스트 감시 모드 |
| `npm run gen:api` | `contracts/openapi.yaml` 에서 TS 타입 재생성 |

## API 계약과 타입

`contracts/openapi.yaml` 이 프론트엔드 타입, 가짜 API, 백엔드 구현 검증의 공통 기준입니다.
계약을 수정했다면:

```bash
npm run gen:api
npm run typecheck
npm test
```

생성 결과는 `src/shared/api/generated/schema.d.ts` 이며 직접 수정하지 않습니다.

## 디렉토리 구조

```
src/
  app/        앱 셸 (App, 라우트, 가드, ApiClient 선택, QueryClient)
  shared/
    api/      ApiClient 인터페이스, realClient, 오류 정규화, 인증 브리지, 생성된 타입
    sse/      SSE 파서, useEventStream (재연결)
    ui/       Button, Modal, ConfirmDialog, Toast, FormField, StatusBadge 등
    utils/    포맷터, 입력 검증, 오류 문구
  customer/   고객 화면 (인증, 장바구니, 메뉴, 주문, 주문 내역)
  admin/      관리자 화면 (인증, 실시간, 대시보드, 테이블, 메뉴)
  mocks/      인-메모리 가짜 백엔드 (계약 동작 재현)
  styles/     전역 스타일(디자인 토큰)
  test/       테스트 공통 설정과 renderWithProviders
```

## 라우트

| 경로 | 화면 |
|---|---|
| `/customer/setup` | 테이블 초기 설정 |
| `/customer/menu` | 메뉴 + 장바구니 (기본) |
| `/customer/orders` | 현재 세션 주문 내역 |
| `/customer/order-complete` | 주문 완료 (5초 후 메뉴로) |
| `/admin/login` | 관리자 로그인 |
| `/admin/dashboard` | 실시간 주문 대시보드 |
| `/admin/tables` | 테이블 등록/관리 |
| `/admin/menus` | 메뉴 관리 |

## 백엔드 구현 시 유의 (계약 요구)

- 주문 생성은 `clientOrderId`로 멱등해야 합니다 (같은 ID 재전송 시 기존 주문 반환).
- `GET /api/admin/dashboard?table=N` 은 해당 테이블의 현재 세션 전체 주문을 반환합니다.
- SSE `order_created` 이벤트의 `payload.orderId` 를 포함해주세요 (신규 주문 강조에 사용).
- 오류 본문은 `{ code, message?, fields?, retryAfterSeconds?, details? }` 형식입니다.
