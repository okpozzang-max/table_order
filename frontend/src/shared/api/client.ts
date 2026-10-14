import { createContext, useContext } from 'react'
import type {
  AdminLoginRequest,
  CategoryMenus,
  HistoryOrder,
  Menu,
  MenuInput,
  Order,
  OrderCreateRequest,
  OrderPage,
  OrderStatus,
  ServerEvent,
  SessionSummary,
  TableInfo,
  TableLoginRequest,
  TableRegisterRequest,
  TableSummary,
  TableTokenResponse,
  TokenResponse,
} from './types'

export interface EventStreamOptions {
  /** abort되면 스트림을 닫고 resolve한다 */
  signal: AbortSignal
  /** 연결이 성립(응답 헤더 수신)되었을 때 */
  onOpen(): void
  onEvent(event: ServerEvent): void
}

/** 계약(contracts/openapi.yaml)의 19개 operation에 1:1 대응한다. */
export interface ApiClient {
  // customer
  customerLogin(req: TableLoginRequest): Promise<TableTokenResponse>
  getCustomerMenus(): Promise<CategoryMenus[]>
  createOrder(req: OrderCreateRequest): Promise<Order>
  listSessionOrders(page: number, size: number): Promise<OrderPage>
  // admin auth
  adminLogin(req: AdminLoginRequest): Promise<TokenResponse>
  // admin orders
  getDashboard(table?: number | null): Promise<TableSummary[]>
  getOrder(orderId: number): Promise<Order>
  changeOrderStatus(orderId: number, status: OrderStatus): Promise<Order>
  deleteOrder(orderId: number): Promise<TableSummary>
  /** 연결이 끝나면(서버 종료/오류) resolve 또는 reject. abort 시 resolve. 재연결은 호출 측(useEventStream)이 담당 */
  streamAdminEvents(opts: EventStreamOptions): Promise<void>
  // admin tables
  listTables(): Promise<TableInfo[]>
  registerTable(req: TableRegisterRequest): Promise<TableInfo>
  endSession(tableId: number): Promise<SessionSummary>
  getTableHistory(tableId: number, range?: { from?: string; to?: string }): Promise<HistoryOrder[]>
  // admin menus
  listAdminMenus(): Promise<CategoryMenus[]>
  createMenu(input: MenuInput): Promise<Menu>
  updateMenu(menuId: number, input: MenuInput): Promise<Menu>
  deleteMenu(menuId: number): Promise<void>
  reorderMenus(category: string, orderedIds: number[]): Promise<void>
}

export const ApiClientContext = createContext<ApiClient | null>(null)

export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext)
  if (!client) {
    throw new Error('ApiClientContext.Provider 안에서만 useApiClient를 사용할 수 있어요.')
  }
  return client
}
