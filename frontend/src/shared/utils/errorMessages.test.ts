import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/errors'
import { ADMIN_LOGIN_ERROR_MESSAGES, lockedMessage, messageForCode, messageForError, ORDER_ERROR_MESSAGES } from './errorMessages'
import type { ErrorCode } from '../api/types'

const ALL_CODES: ErrorCode[] = [
  'NETWORK_ERROR',
  'INVALID_CREDENTIALS',
  'UNAUTHORIZED',
  'ACCOUNT_LOCKED',
  'VALIDATION_ERROR',
  'NOT_FOUND',
  'MENU_UNAVAILABLE',
  'PRICE_CHANGED',
  'INVALID_TRANSITION',
  'NO_ACTIVE_SESSION',
  'DUPLICATE_TABLE',
  'INTERNAL_ERROR',
]

describe('errorMessages', () => {
  it('모든 오류 코드에 한국어 문구가 있다', () => {
    for (const code of ALL_CODES) {
      expect(messageForCode(code).length).toBeGreaterThan(0)
    }
  })

  it('컨텍스트별 문구가 기본값을 덮어쓴다', () => {
    expect(messageForCode('NETWORK_ERROR', ORDER_ERROR_MESSAGES)).toContain('주문')
    expect(messageForCode('INVALID_CREDENTIALS', ADMIN_LOGIN_ERROR_MESSAGES)).toContain('사용자명')
    expect(messageForCode('NOT_FOUND', ORDER_ERROR_MESSAGES)).toBe(messageForCode('NOT_FOUND'))
  })

  it('ApiError가 아니면 일반 오류 문구', () => {
    expect(messageForError(new Error('x'))).toBe(messageForCode('INTERNAL_ERROR'))
    expect(messageForError(new ApiError(409, 'PRICE_CHANGED'))).toBe(messageForCode('PRICE_CHANGED'))
  })

  it('잠금 문구에 남은 시간을 포함한다', () => {
    expect(lockedMessage(900)).toContain('15분 00초')
  })
})
