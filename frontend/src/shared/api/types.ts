import type { components } from './generated/schema'

type S = components['schemas']

export type ServerErrorCode = S['ErrorCode']
/** 서버 오류 코드 + 클라이언트가 만드는 NETWORK_ERROR */
export type ErrorCode = ServerErrorCode | 'NETWORK_ERROR'

export type ApiErrorBody = S['ApiErrorBody']
export type OrderStatus = S['OrderStatus']

export type TableLoginRequest = S['TableLoginRequest']
export type AdminLoginRequest = S['AdminLoginRequest']
export type TokenResponse = S['TokenResponse']
export type TableTokenResponse = S['TableTokenResponse']

export type Menu = S['Menu']
export type CategoryMenus = S['CategoryMenus']
export type MenuInput = S['MenuInput']
export type ReorderRequest = S['ReorderRequest']

export type OrderItem = S['OrderItem']
export type Order = S['Order']
export type OrderCreateItem = S['OrderCreateItem']
export type OrderCreateRequest = S['OrderCreateRequest']
export type OrderPage = S['OrderPage']

export type TableSummary = S['TableSummary']
export type TableInfo = S['TableInfo']
export type TableRegisterRequest = S['TableRegisterRequest']
export type SessionSummary = S['SessionSummary']
export type HistoryOrder = S['HistoryOrder']

export type ServerEvent = S['ServerEvent']
export type ServerEventType = ServerEvent['type']

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  PENDING: '대기중',
  PREPARING: '준비중',
  COMPLETED: '완료',
}

/** 순차 전이: 현재 상태에서 갈 수 있는 다음 상태 (없으면 null) */
export const NEXT_ORDER_STATUS: Record<OrderStatus, OrderStatus | null> = {
  PENDING: 'PREPARING',
  PREPARING: 'COMPLETED',
  COMPLETED: null,
}

/** "다음 단계" 버튼 문구 (현재 상태 기준) */
export const NEXT_ACTION_LABEL: Record<OrderStatus, string | null> = {
  PENDING: '준비 시작',
  PREPARING: '완료 처리',
  COMPLETED: null,
}
