import { ApiError } from '../api/errors'
import type { ErrorCode } from '../api/types'
import { formatRemaining } from './format'

const DEFAULT_MESSAGES: Record<ErrorCode, string> = {
  NETWORK_ERROR: '네트워크에 연결할 수 없어요. 잠시 후 다시 시도해주세요.',
  INVALID_CREDENTIALS: '로그인 정보가 맞지 않아요.',
  UNAUTHORIZED: '로그인이 만료되었어요. 다시 로그인해주세요.',
  ACCOUNT_LOCKED: '로그인 시도가 너무 많아요. 잠시 후 다시 시도해주세요.',
  VALIDATION_ERROR: '입력한 내용을 확인해주세요.',
  NOT_FOUND: '대상을 찾을 수 없어요. 이미 삭제되었을 수 있어요.',
  MENU_UNAVAILABLE: '판매하지 않는 메뉴가 포함되어 있어요.',
  PRICE_CHANGED: '메뉴 가격이 변경되었어요.',
  INVALID_TRANSITION: '이미 상태가 변경되었어요. 최신 상태로 갱신했어요.',
  NO_ACTIVE_SESSION: '이미 이용 완료된 테이블이에요.',
  DUPLICATE_TABLE: '이미 등록된 테이블 번호예요.',
  INTERNAL_ERROR: '문제가 발생했어요. 잠시 후 다시 시도해주세요.',
}

/** 컨텍스트별로 기본 문구를 덮어쓸 때 사용 (예: 주문, 관리자 로그인) */
export type MessageOverrides = Partial<Record<ErrorCode, string>>

export const ORDER_ERROR_MESSAGES: MessageOverrides = {
  NETWORK_ERROR: '주문을 보내지 못했어요. 잠시 후 다시 시도해주세요.',
  INTERNAL_ERROR: '주문을 보내지 못했어요. 잠시 후 다시 시도해주세요.',
}

export const TABLE_LOGIN_ERROR_MESSAGES: MessageOverrides = {
  INVALID_CREDENTIALS: '로그인 정보가 맞지 않아요. 관리자에게 문의해주세요.',
}

export const ADMIN_LOGIN_ERROR_MESSAGES: MessageOverrides = {
  INVALID_CREDENTIALS: '매장 식별자, 사용자명 또는 비밀번호가 맞지 않아요.',
}

export function messageForCode(code: ErrorCode, overrides?: MessageOverrides): string {
  return overrides?.[code] ?? DEFAULT_MESSAGES[code]
}

export function messageForError(err: unknown, overrides?: MessageOverrides): string {
  if (err instanceof ApiError) return messageForCode(err.code, overrides)
  return messageForCode('INTERNAL_ERROR', overrides)
}

export function lockedMessage(seconds: number): string {
  return `로그인 시도가 너무 많아요. ${formatRemaining(seconds)} 후 다시 시도해주세요.`
}
