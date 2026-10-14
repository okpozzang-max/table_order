import { describe, expect, it } from 'vitest'
import { cartSignature, formatDateTime, formatKRW, formatRemaining, summarizeItems } from './format'

describe('format', () => {
  it('금액을 천 단위 구분 + 원으로 표시한다', () => {
    expect(formatKRW(12000)).toBe('12,000원')
    expect(formatKRW(0)).toBe('0원')
  })

  it('날짜를 YYYY-MM-DD HH:mm 로컬 형식으로 표시한다', () => {
    const d = new Date(2026, 9, 14, 9, 5)
    expect(formatDateTime(d.toISOString())).toBe('2026-10-14 09:05')
    expect(formatDateTime('invalid')).toBe('')
  })

  it('메뉴 요약: 1개면 이름만, 여러 개면 외 N건', () => {
    expect(summarizeItems([])).toBe('')
    expect(summarizeItems([{ menuName: '김치찌개' }])).toBe('김치찌개')
    expect(summarizeItems([{ menuName: '김치찌개' }, { menuName: '공기밥' }, { menuName: '콜라' }])).toBe(
      '김치찌개 외 2건',
    )
  })

  it('장바구니 서명은 순서와 무관하다', () => {
    const a = cartSignature([
      { menuId: 2, quantity: 1 },
      { menuId: 1, quantity: 3 },
    ])
    const b = cartSignature([
      { menuId: 1, quantity: 3 },
      { menuId: 2, quantity: 1 },
    ])
    expect(a).toBe(b)
    expect(a).toBe('1:3,2:1')
    expect(cartSignature([{ menuId: 1, quantity: 4 }])).not.toBe(a)
  })

  it('남은 시간을 분/초로 표시한다', () => {
    expect(formatRemaining(900)).toBe('15분 00초')
    expect(formatRemaining(65)).toBe('1분 05초')
    expect(formatRemaining(9)).toBe('9초')
    expect(formatRemaining(-3)).toBe('0초')
  })
})
