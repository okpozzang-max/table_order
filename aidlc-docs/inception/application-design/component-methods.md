# Component Methods (메서드 시그니처)

상세 비즈니스 규칙(검증 상세, 전이 표, 트랜잭션 경계, 스키마)은 Functional Design(CONSTRUCTION)에서 정의합니다. 여기서는 시그니처와 목적만 둡니다.

표기: Python 타입 힌트. `Conn`은 `sqlite3.Connection`. 서비스 메서드는 동기(`def`)이며 FastAPI 스레드풀에서 실행됩니다.

---

## 백엔드

### Config / Database / Security

```python
# config.py
class Settings:  # .env 값
    store_id: str
    admin_username: str
    admin_password_hash: str
    jwt_secret: str
    db_path: str
    token_ttl_hours: int = 16
    login_max_failures: int = 5
    login_lock_minutes: int = 15

def get_settings() -> Settings: ...          # 설정 로드 (필수값 누락 시 시작 실패)

# db.py
def get_connection() -> Conn: ...            # 요청 단위 연결 (WAL, foreign_keys=ON)
def transaction(conn: Conn) -> ContextManager[Conn]: ...  # 커밋/롤백 보장
def init_schema(conn: Conn) -> None: ...     # 테이블 생성 (없으면)

# security.py
def hash_password(plain: str) -> str: ...
def verify_password(plain: str, hashed: str) -> bool: ...
def create_token(subject: str, role: str, extra: dict, ttl_hours: int) -> str: ...  # role: "admin" | "table"
def decode_token(token: str) -> TokenClaims: ...   # 만료/위변조 시 AuthError

# deps.py
def require_admin(authorization: str) -> AdminPrincipal: ...   # 실패 시 401
def require_table(authorization: str) -> TablePrincipal: ...   # 실패 시 401
```

### EventBroker

```python
# events.py
class Event:  # type: "order_created" | "order_status_changed" | "order_deleted" | "session_ended" | "menu_changed"
    type: str
    table_id: int | None
    payload: dict

class EventBroker:
    def publish(self, event: Event) -> None: ...                 # 스레드 안전, 논블로킹
    def subscribe(self) -> AsyncIterator[Event]: ...             # 연결 종료 시 자동 해제
```

### AuthService

```python
class AuthService:
    def login_admin(self, store_id: str, username: str, password: str, client_key: str) -> TokenResult: ...
        # 잠금 확인 -> 검증 -> 실패 기록/성공 시 초기화 -> 토큰 발급. 잠금 시 AccountLockedError(remaining_seconds)
    def login_table(self, store_id: str, table_number: int, password: str) -> TableTokenResult: ...
        # 검증 성공 시 table 토큰 발급, 실패 시 InvalidCredentialsError
```

### MenuService

```python
class MenuService:
    def list_menus_grouped(self) -> list[CategoryMenus]: ...         # 고객/관리자 공용 조회, 노출 순서 반영
    def create_menu(self, data: MenuCreate) -> Menu: ...             # 검증 실패 시 ValidationError(fields)
    def update_menu(self, menu_id: int, data: MenuUpdate) -> Menu: ...
    def delete_menu(self, menu_id: int) -> None: ...
    def reorder_menus(self, category: str, ordered_ids: list[int]) -> None: ...
```

### TableService

```python
class TableService:
    def register_table(self, table_number: int, password: str) -> Table: ...      # 비밀번호는 해시 저장
    def list_tables(self) -> list[Table]: ...
    def get_or_start_session(self, conn: Conn, table_id: int) -> TableSession: ...  # 첫 주문 시 새 세션 (OrderService가 트랜잭션 내 호출)
    def end_session(self, table_id: int) -> SessionSummary: ...                    # 주문을 이력으로 이관, 현재 합계 0, 이벤트 발행
    def list_history(self, table_id: int, date_from: date | None, date_to: date | None) -> list[HistoryOrder]: ...
```

### OrderService

```python
class OrderService:
    def create_order(self, table: TablePrincipal, items: list[OrderItemIn], client_total: int | None) -> OrderOut: ...
        # 메뉴 존재 확인, 서버 가격으로 합계 재계산, 세션 확보, 저장, order_created 발행
    def list_session_orders(self, table: TablePrincipal, page: int, size: int) -> Page[OrderOut]: ...
    def dashboard_snapshot(self, table_filter: int | None, preview_count: int) -> list[TableSummary]: ...
    def get_order(self, order_id: int) -> OrderDetail: ...
    def change_status(self, order_id: int, new_status: OrderStatus) -> OrderOut: ...   # 순차 전이만, 아니면 InvalidTransitionError
    def delete_order(self, order_id: int) -> TableSummary: ...                         # 삭제 후 합계 재계산, order_deleted 발행
```

### Routers (`/api` 하위)

| 라우터 | 메서드 경로 | 인증 | 서비스 호출 |
|---|---|---|---|
| customer_auth | `POST /api/customer/auth/login` | 없음 | `login_table` |
| customer_menu | `GET /api/customer/menus` | table | `list_menus_grouped` |
| customer_orders | `POST /api/customer/orders` | table | `create_order` |
| customer_orders | `GET /api/customer/orders?page=&size=` | table | `list_session_orders` |
| admin_auth | `POST /api/admin/auth/login` | 없음 | `login_admin` |
| admin_orders | `GET /api/admin/dashboard?table=` | admin | `dashboard_snapshot` |
| admin_orders | `GET /api/admin/orders/{id}` | admin | `get_order` |
| admin_orders | `PATCH /api/admin/orders/{id}/status` | admin | `change_status` |
| admin_orders | `DELETE /api/admin/orders/{id}` | admin | `delete_order` |
| admin_orders | `GET /api/admin/events` (SSE) | admin | `EventBroker.subscribe` |
| admin_tables | `GET /api/admin/tables` | admin | `list_tables` |
| admin_tables | `POST /api/admin/tables` | admin | `register_table` |
| admin_tables | `POST /api/admin/tables/{id}/end-session` | admin | `end_session` |
| admin_tables | `GET /api/admin/tables/{id}/history?from=&to=` | admin | `list_history` |
| admin_menus | `GET /api/admin/menus` | admin | `list_menus_grouped` |
| admin_menus | `POST /api/admin/menus` | admin | `create_menu` |
| admin_menus | `PUT /api/admin/menus/{id}` | admin | `update_menu` |
| admin_menus | `DELETE /api/admin/menus/{id}` | admin | `delete_menu` |
| admin_menus | `PUT /api/admin/menus/reorder` | admin | `reorder_menus` |

도메인 오류 -> HTTP 상태코드: ValidationError 422, InvalidCredentialsError/AuthError 401, AccountLockedError 429, NotFoundError 404, InvalidTransitionError/SessionClosedError 409.

### SSE 이벤트 규격 (요약)
- 스트림: `text/event-stream`, 이벤트 이름은 Event.type, 데이터는 JSON(`table_id`, `payload`)
- 연결 유지용 주기적 주석(keep-alive) 전송
- 클라이언트는 이벤트 수신 시 대시보드 쿼리를 무효화하여 재조회하고, 재연결 직후에도 재조회한다.

---

## 프론트엔드

### Shared

```ts
// shared/api/client.ts
function apiRequest<T>(path: string, opts?: { method?: string; body?: unknown; auth?: 'admin' | 'table' | 'none' }): Promise<T>
// 오류는 ApiError { status, code, message, fields? } 로 정규화, 401은 인증 컨텍스트에 통지

// shared/sse/useEventStream.ts
function useEventStream(opts: { url: string; token: string; onEvent: (e: ServerEvent) => void; onReconnect: () => void }): { status: 'connecting' | 'open' | 'closed' }

function formatKRW(amount: number): string
```

### Customer

```ts
// TableAuthProvider
interface TableAuthContext {
  status: 'loading' | 'authenticated' | 'needs_setup' | 'error'
  table: { tableNumber: number } | null
  setup(storeId: string, tableNumber: number, password: string): Promise<void>  // 성공 시 localStorage 저장
  logout(): void
}

// CartProvider
interface CartContext {
  items: CartItem[]          // { menuId, name, unitPrice, quantity }
  total: number
  add(menu: Menu): void
  remove(menuId: number): void
  increase(menuId: number): void
  decrease(menuId: number): void   // 수량 1에서 감소하면 항목 제거
  clear(): void
}

// 데이터 훅 (TanStack Query)
useMenus(): Query<CategoryMenus[]>
useCreateOrder(): Mutation<OrderOut, OrderCreateInput>
useSessionOrders(page: number): Query<Page<OrderOut>>   // refetchInterval 5~10초
```

### Admin

```ts
// AdminAuthProvider
interface AdminAuthContext {
  isAuthenticated: boolean
  login(storeId: string, username: string, password: string): Promise<void>
  logout(): void
}

// 데이터 훅
useDashboard(tableFilter?: number): Query<TableSummary[]>   // SSE 이벤트로 무효화
useOrderDetail(orderId: number): Query<OrderDetail>
useChangeOrderStatus(): Mutation<OrderOut, { orderId: number; status: OrderStatus }>
useDeleteOrder(): Mutation<TableSummary, number>
useTables(): Query<Table[]>
useRegisterTable(): Mutation<Table, { tableNumber: number; password: string }>
useEndSession(): Mutation<SessionSummary, number>
useTableHistory(tableId: number, range?: DateRange): Query<HistoryOrder[]>
useMenusAdmin(): Query<CategoryMenus[]>
useCreateMenu() / useUpdateMenu() / useDeleteMenu() / useReorderMenus(): Mutation
```
