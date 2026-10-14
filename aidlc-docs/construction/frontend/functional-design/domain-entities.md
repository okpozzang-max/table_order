# Domain Entities - frontend (Unit 1)

프론트엔드가 다루는 데이터의 형태입니다. API DTO의 최종 기준은 `contracts/openapi.yaml`(Code Generation 초반에 작성)이며, 여기에 적은 필드는 그 계약의 초안입니다. 계약에 반영되면 TS 타입은 `openapi-typescript`로 자동 생성됩니다.

---

## 1. 열거형 (Enumerations)

| 이름 | 값 | 화면 표시 |
|---|---|---|
| `OrderStatus` | `PENDING` | 대기중 |
| | `PREPARING` | 준비중 |
| | `COMPLETED` | 완료 |
| `ServerEventType` | `order_created`, `order_status_changed`, `order_deleted`, `session_ended`, `menu_changed` | (표시 안 함) |
| `ErrorCode` | 5절 참고 | 한국어 문구 매핑 |

상태 전이: `PENDING -> PREPARING -> COMPLETED` (역방향/건너뛰기 불가).

---

## 2. API DTO (서버와 주고받는 형태)

### 인증
```ts
interface TableLoginRequest  { storeId: string; tableNumber: number; password: string }
interface AdminLoginRequest  { storeId: string; username: string; password: string }
interface TokenResponse      { accessToken: string; expiresAt: string /* ISO 8601 */ }
interface TableTokenResponse extends TokenResponse { tableId: number; tableNumber: number }
```

### 메뉴
```ts
interface Menu {
  id: number
  name: string
  price: number            // 원, 정수
  description: string      // 빈 문자열 가능
  category: string
  imageUrl: string | null
  displayOrder: number     // 카테고리 내 노출 순서
}
interface CategoryMenus { category: string; menus: Menu[] }   // 카테고리 순서는 서버가 정한 순서
interface MenuInput { name: string; price: number; description: string; category: string; imageUrl: string | null }
```

### 주문
```ts
interface OrderItem { menuId: number; menuName: string; quantity: number; unitPrice: number }
interface Order {
  id: number
  orderNumber: string      // 화면에 표시되는 주문 번호
  tableId: number
  tableNumber: number
  sessionId: string
  createdAt: string        // ISO 8601
  status: OrderStatus
  totalAmount: number
  items: OrderItem[]
}
interface OrderCreateRequest {
  clientOrderId: string    // 클라이언트가 생성한 UUID. 재시도 시 중복 주문 방지용
  items: { menuId: number; quantity: number }[]
  clientTotal: number      // 클라이언트 계산 합계 (서버가 검증)
}
interface Page<T> { items: T[]; page: number; size: number; hasNext: boolean }
```

### 관리자 대시보드/테이블
```ts
interface TableSummary {
  tableId: number
  tableNumber: number
  sessionActive: boolean
  totalAmount: number      // 현재 세션 총 주문액
  orderCount: number
  orders: Order[]          // table 필터가 없으면 최신 3건, 특정 table 필터면 현재 세션의 전체 주문 (최신순)
}
interface TableInfo { id: number; tableNumber: number; sessionActive: boolean }
interface TableRegisterRequest { tableNumber: number; password: string }
interface HistoryOrder {
  orderId: number; orderNumber: string; tableNumber: number
  createdAt: string; items: OrderItem[]; totalAmount: number
  completedAt: string      // 이용 완료 시각
}
interface ServerEvent { type: ServerEventType; tableId: number | null; payload: Record<string, unknown> }
```

### 오류
```ts
interface ApiErrorBody {
  code: ErrorCode
  message?: string
  fields?: Record<string, string>      // VALIDATION_ERROR 시 필드별 사유
  retryAfterSeconds?: number           // ACCOUNT_LOCKED 시
  details?: { menuIds?: number[]; currentPrices?: { menuId: number; price: number }[] }
}
class ApiError extends Error { status: number; code: ErrorCode | 'NETWORK_ERROR'; body?: ApiErrorBody }
```

> 백엔드 Unit으로 넘기는 계약 요구: (1) `OrderCreateRequest.clientOrderId`로 중복 주문 방지(같은 ID 재전송 시 기존 주문을 반환), (2) `GET /api/admin/dashboard?table=N`은 해당 테이블의 현재 세션 전체 주문을 반환, (3) 목록 응답은 `Page<T>`(page, size, hasNext), (4) 위 오류 코드/필드 형식.

---

## 3. 클라이언트 전용 모델

### CartItem / Cart
```ts
interface CartItem { menuId: number; name: string; unitPrice: number; quantity: number }   // 1 <= quantity <= 20
interface Cart { items: CartItem[] }
// 파생값: totalAmount = sum(unitPrice * quantity), totalCount = sum(quantity)
```

### 인증 상태
```ts
type TableAuthStatus = 'loading' | 'authenticated' | 'needs_setup' | 'error'
interface TableAuthState {
  status: TableAuthStatus
  tableNumber: number | null
  errorMessage?: string          // needs_setup 이유 또는 error 사유
}
interface AdminAuthState { isAuthenticated: boolean; expiresAt: string | null }
```

### 관리자 실시간 상태
```ts
type StreamStatus = 'connecting' | 'open' | 'reconnecting'
type UnseenOrders = Record<number /* tableId */, number[] /* orderId */>   // 메모리에만 유지
```

---

## 4. 브라우저 저장소 스키마

| 키 | 저장소 | 값 | 수명/정리 |
|---|---|---|---|
| `tableorder.table.credentials` | localStorage | `{ storeId, tableNumber, password }` | 초기 설정 성공 시 저장. 설정 화면에서 다시 설정하면 덮어씀 |
| `tableorder.cart.v1` | localStorage | `{ tableKey: "<storeId>:<tableNumber>", items: CartItem[] }` | 주문 성공/비우기 시 비움. `tableKey`가 현재 테이블과 다르면 버림 |
| `tableorder.pendingOrder.v1` | localStorage | `{ clientOrderId, cartSignature }` | 주문 확정 시도 중 보관. 성공하거나 장바구니 내용이 바뀌면 삭제 |
| `tableorder.admin.auth` | localStorage | `{ accessToken, expiresAt }` | 로그인 시 저장. 만료/로그아웃/401 시 삭제 |
| `tableorder.mock.store.v1` (mock 모드 전용) | localStorage | 가짜 API 데이터 전체 | 개발/테스트용. 실제 모드에서는 사용 안 함 |

- 테이블(고객) 토큰은 **메모리에만** 둔다. 앱 시작 시 저장된 자격 증명으로 매번 로그인해 발급받는다.
- `cartSignature`는 항목(메뉴ID, 수량) 정렬 문자열이다. 장바구니가 바뀌면 `clientOrderId`를 새로 만든다.

---

## 5. 오류 코드

| 코드 | HTTP | 의미 |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | 로그인 정보 불일치 |
| `UNAUTHORIZED` | 401 | 토큰 없음/만료/위변조 |
| `ACCOUNT_LOCKED` | 429 | 로그인 실패 누적으로 잠금 (`retryAfterSeconds`) |
| `VALIDATION_ERROR` | 422 | 입력 검증 실패 (`fields`) |
| `NOT_FOUND` | 404 | 대상 없음 (메뉴, 주문, 테이블) |
| `MENU_UNAVAILABLE` | 409 | 주문에 삭제된 메뉴 포함 (`details.menuIds`) |
| `PRICE_CHANGED` | 409 | 서버 가격과 장바구니 가격 불일치 (`details.currentPrices`) |
| `INVALID_TRANSITION` | 409 | 허용되지 않는 주문 상태 전이 |
| `NO_ACTIVE_SESSION` | 409 | 활성 세션이 없는 테이블의 이용 완료 요청 |
| `DUPLICATE_TABLE` | 409 | 이미 등록된 테이블 번호 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |
| `NETWORK_ERROR` | - | (클라이언트 생성) 네트워크 불가/타임아웃 |

---

## 6. 엔티티 관계 (요약)

```
Menu (n) --- (1) Category(문자열)
CartItem (n) --- (1) Menu          (menuId 참조, name/unitPrice는 담을 때의 스냅샷)
Order (1) --- (n) OrderItem
TableSummary (1) --- (n) Order     (현재 세션)
HistoryOrder                        (종료된 세션의 주문, 읽기 전용)
```
