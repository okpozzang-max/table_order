import { beforeEach, describe, expect, it } from 'vitest'
import { MockBackend } from './mockBackend'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from './seed'
import type { ServerEvent } from '../shared/api/types'

let clock = 1_700_000_000_000
let be: MockBackend

function adminToken(): string {
  return be.adminLogin({ storeId: MOCK_STORE_ID, username: MOCK_ADMIN_USERNAME, password: MOCK_ADMIN_PASSWORD })
    .accessToken
}

function tableToken(tableNumber = 1): string {
  return be.customerLogin({ storeId: MOCK_STORE_ID, tableNumber, password: MOCK_TABLE_PASSWORD }).accessToken
}

function orderBody(items: { menuId: number; quantity: number }[], clientOrderId = crypto.randomUUID()) {
  const menus = be.getCustomerMenus(tableToken()).flatMap((c) => c.menus)
  const total = items.reduce((s, i) => s + (menus.find((m) => m.id === i.menuId)?.price ?? 0) * i.quantity, 0)
  return { clientOrderId, items, clientTotal: total }
}

beforeEach(() => {
  clock = 1_700_000_000_000
  be = new MockBackend({ now: () => clock })
})

describe('MockBackend - 인증', () => {
  it('테이블 로그인 성공/실패', () => {
    expect(tableToken(2)).toContain('mock-table')
    expect(() => be.customerLogin({ storeId: MOCK_STORE_ID, tableNumber: 1, password: '9999' })).toThrowError(
      expect.objectContaining({ code: 'INVALID_CREDENTIALS' }),
    )
    expect(() => be.customerLogin({ storeId: MOCK_STORE_ID, tableNumber: 1, password: 'abc' })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    )
  })

  it('만료된 토큰은 UNAUTHORIZED', () => {
    const token = tableToken()
    clock += 16 * 3600 * 1000 + 1
    expect(() => be.getCustomerMenus(token)).toThrowError(expect.objectContaining({ code: 'UNAUTHORIZED' }))
  })

  it('관리자 토큰으로 테이블 API 접근 불가', () => {
    expect(() => be.getCustomerMenus(adminToken())).toThrowError(expect.objectContaining({ code: 'UNAUTHORIZED' }))
    expect(() => be.listTables(tableToken())).toThrowError(expect.objectContaining({ code: 'UNAUTHORIZED' }))
  })

  it('관리자 로그인 5회 실패 시 15분 잠금, 이후 해제', () => {
    const bad = { storeId: MOCK_STORE_ID, username: MOCK_ADMIN_USERNAME, password: 'wrong' }
    for (let i = 0; i < 4; i++) {
      expect(() => be.adminLogin(bad)).toThrowError(expect.objectContaining({ code: 'INVALID_CREDENTIALS' }))
    }
    expect(() => be.adminLogin(bad)).toThrowError(
      expect.objectContaining({ code: 'ACCOUNT_LOCKED', body: expect.objectContaining({ retryAfterSeconds: 900 }) }),
    )
    // 잠금 중에는 올바른 정보로도 실패
    expect(() =>
      be.adminLogin({ storeId: MOCK_STORE_ID, username: MOCK_ADMIN_USERNAME, password: MOCK_ADMIN_PASSWORD }),
    ).toThrowError(expect.objectContaining({ code: 'ACCOUNT_LOCKED' }))
    clock += 15 * 60 * 1000 + 1000
    expect(adminToken()).toContain('mock-admin')
  })
})

describe('MockBackend - 주문', () => {
  it('주문 생성: 서버 가격으로 합계를 계산하고 첫 주문에서 세션을 시작한다', () => {
    const t = tableToken()
    expect(be.listTables(adminToken()).find((x) => x.tableNumber === 1)?.sessionActive).toBe(false)
    const order = be.createOrder(t, orderBody([{ menuId: 1, quantity: 2 }, { menuId: 6, quantity: 1 }]))
    expect(order.totalAmount).toBe(9000 * 2 + 1000)
    expect(order.status).toBe('PENDING')
    expect(be.listTables(adminToken()).find((x) => x.tableNumber === 1)?.sessionActive).toBe(true)
  })

  it('같은 clientOrderId로 재전송하면 중복 생성되지 않는다', () => {
    const t = tableToken()
    const body = orderBody([{ menuId: 1, quantity: 1 }])
    const a = be.createOrder(t, body)
    const b = be.createOrder(t, body)
    expect(b.id).toBe(a.id)
    expect(be.listSessionOrders(t, 0, 10).items).toHaveLength(1)
  })

  it('클라이언트 합계가 다르면 PRICE_CHANGED 와 현재 가격을 알려준다', () => {
    const t = tableToken()
    try {
      be.createOrder(t, { clientOrderId: crypto.randomUUID(), items: [{ menuId: 1, quantity: 1 }], clientTotal: 1 })
      expect.unreachable()
    } catch (e) {
      expect(e).toMatchObject({ code: 'PRICE_CHANGED', body: { details: { currentPrices: [{ menuId: 1, price: 9000 }] } } })
    }
  })

  it('삭제된 메뉴가 있으면 MENU_UNAVAILABLE', () => {
    const t = tableToken()
    be.deleteMenu(adminToken(), 2)
    try {
      be.createOrder(t, { clientOrderId: crypto.randomUUID(), items: [{ menuId: 2, quantity: 1 }], clientTotal: 8500 })
      expect.unreachable()
    } catch (e) {
      expect(e).toMatchObject({ code: 'MENU_UNAVAILABLE', body: { details: { menuIds: [2] } } })
    }
  })

  it('수량 범위(1~20) 검증', () => {
    const t = tableToken()
    expect(() =>
      be.createOrder(t, { clientOrderId: crypto.randomUUID(), items: [{ menuId: 1, quantity: 21 }], clientTotal: 9000 * 21 }),
    ).toThrowError(expect.objectContaining({ code: 'VALIDATION_ERROR' }))
  })

  it('주문 내역은 최신순이며 페이지네이션된다', () => {
    const t = tableToken()
    for (let i = 0; i < 12; i++) be.createOrder(t, orderBody([{ menuId: 6, quantity: 1 }]))
    const p0 = be.listSessionOrders(t, 0, 10)
    const p1 = be.listSessionOrders(t, 1, 10)
    expect(p0.items).toHaveLength(10)
    expect(p0.hasNext).toBe(true)
    expect(p1.items).toHaveLength(2)
    expect(p1.hasNext).toBe(false)
    expect(p0.items[0].id).toBeGreaterThan(p0.items[1].id)
  })

  it('상태는 순차 전이만 허용한다', () => {
    const a = adminToken()
    const order = be.createOrder(tableToken(), orderBody([{ menuId: 1, quantity: 1 }]))
    expect(() => be.changeOrderStatus(a, order.id, 'COMPLETED')).toThrowError(
      expect.objectContaining({ code: 'INVALID_TRANSITION' }),
    )
    expect(be.changeOrderStatus(a, order.id, 'PREPARING').status).toBe('PREPARING')
    expect(be.changeOrderStatus(a, order.id, 'COMPLETED').status).toBe('COMPLETED')
    expect(() => be.changeOrderStatus(a, order.id, 'PREPARING')).toThrowError(
      expect.objectContaining({ code: 'INVALID_TRANSITION' }),
    )
  })

  it('주문 삭제 후 테이블 합계가 재계산된다', () => {
    const a = adminToken()
    const t = tableToken()
    const o1 = be.createOrder(t, orderBody([{ menuId: 1, quantity: 1 }]))
    be.createOrder(t, orderBody([{ menuId: 6, quantity: 2 }]))
    const summary = be.deleteOrder(a, o1.id)
    expect(summary.totalAmount).toBe(2000)
    expect(summary.orderCount).toBe(1)
    expect(() => be.deleteOrder(a, o1.id)).toThrowError(expect.objectContaining({ code: 'NOT_FOUND' }))
  })
})

describe('MockBackend - 대시보드와 세션', () => {
  it('대시보드는 테이블 번호 순, 기본은 최신 3건, table 필터는 전체', () => {
    const a = adminToken()
    const t = tableToken(2)
    for (let i = 0; i < 5; i++) be.createOrder(t, orderBody([{ menuId: 6, quantity: 1 }]))
    const all = be.getDashboard(a)
    expect(all.map((x) => x.tableNumber)).toEqual([1, 2, 3, 4, 5])
    const t2 = all.find((x) => x.tableNumber === 2)!
    expect(t2.orderCount).toBe(5)
    expect(t2.orders).toHaveLength(3)
    expect(t2.totalAmount).toBe(5000)
    const only = be.getDashboard(a, 2)
    expect(only).toHaveLength(1)
    expect(only[0].orders).toHaveLength(5)
    expect(() => be.getDashboard(a, 99)).toThrowError(expect.objectContaining({ code: 'NOT_FOUND' }))
  })

  it('이용 완료: 주문이 이력으로 이동하고 합계가 0이 되며 새 세션은 빈 상태로 시작', () => {
    const a = adminToken()
    const t = tableToken()
    be.createOrder(t, orderBody([{ menuId: 1, quantity: 1 }]))
    be.createOrder(t, orderBody([{ menuId: 6, quantity: 1 }]))
    const summary = be.endSession(a, 1)
    expect(summary.archivedOrderCount).toBe(2)
    expect(summary.archivedTotalAmount).toBe(10000)

    const after = be.getDashboard(a, 1)[0]
    expect(after.totalAmount).toBe(0)
    expect(after.sessionActive).toBe(false)
    expect(be.listSessionOrders(t, 0, 10).items).toHaveLength(0)

    const history = be.getTableHistory(a, 1)
    expect(history).toHaveLength(2)
    expect(history[0].completedAt).toBe(summary.endedAt)

    const next = be.createOrder(t, orderBody([{ menuId: 6, quantity: 1 }]))
    expect(next.sessionId).not.toBe(history.length ? 'S-1-1' : '')
    expect(be.listSessionOrders(t, 0, 10).items).toHaveLength(1)
  })

  it('활성 세션이 없으면 NO_ACTIVE_SESSION', () => {
    expect(() => be.endSession(adminToken(), 3)).toThrowError(expect.objectContaining({ code: 'NO_ACTIVE_SESSION' }))
  })

  it('과거 내역 날짜 필터', () => {
    const a = adminToken()
    const t = tableToken()
    be.createOrder(t, orderBody([{ menuId: 6, quantity: 1 }]))
    be.endSession(a, 1)
    const d = new Date(clock)
    const p = (n: number) => String(n).padStart(2, '0')
    const today = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
    expect(be.getTableHistory(a, 1, { from: today, to: today })).toHaveLength(1)
    expect(be.getTableHistory(a, 1, { from: '2000-01-01', to: '2000-01-02' })).toHaveLength(0)
    expect(() => be.getTableHistory(a, 1, { from: '2026-10-10', to: '2026-10-01' })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    )
  })

  it('테이블 등록: 중복과 형식 검증', () => {
    const a = adminToken()
    expect(be.registerTable(a, { tableNumber: 10, password: '0010' })).toMatchObject({ tableNumber: 10, sessionActive: false })
    expect(() => be.registerTable(a, { tableNumber: 10, password: '0010' })).toThrowError(
      expect.objectContaining({ code: 'DUPLICATE_TABLE' }),
    )
    expect(() => be.registerTable(a, { tableNumber: 0, password: 'ab' })).toThrowError(
      expect.objectContaining({ code: 'VALIDATION_ERROR' }),
    )
    // 등록한 테이블로 로그인 가능
    expect(be.customerLogin({ storeId: MOCK_STORE_ID, tableNumber: 10, password: '0010' }).tableNumber).toBe(10)
  })
})

describe('MockBackend - 메뉴와 이벤트', () => {
  it('메뉴 등록/수정/삭제와 검증', () => {
    const a = adminToken()
    const created = be.createMenu(a, { name: '라면', price: 4000, description: '', category: '분식', imageUrl: null })
    expect(be.listAdminMenus(a).some((c) => c.category === '분식')).toBe(true)
    const updated = be.updateMenu(a, created.id, { name: '신라면', price: 4500, description: 'd', category: '분식', imageUrl: 'https://x.test/a.png' })
    expect(updated.price).toBe(4500)
    be.deleteMenu(a, created.id)
    expect(be.listAdminMenus(a).some((c) => c.category === '분식')).toBe(false)

    try {
      be.createMenu(a, { name: '', price: 50, description: '', category: '', imageUrl: 'ftp://x' })
      expect.unreachable()
    } catch (e) {
      expect((e as { body: { fields: Record<string, string> } }).body.fields).toEqual(
        expect.objectContaining({ name: expect.any(String), price: expect.any(String), category: expect.any(String), imageUrl: expect.any(String) }),
      )
    }
  })

  it('메뉴 순서 변경', () => {
    const a = adminToken()
    const main = be.listAdminMenus(a).find((c) => c.category === '메인')!
    const ids = main.menus.map((m) => m.id)
    const reversed = [...ids].reverse()
    be.reorderMenus(a, '메인', reversed)
    expect(be.listAdminMenus(a).find((c) => c.category === '메인')!.menus.map((m) => m.id)).toEqual(reversed)
    expect(() => be.reorderMenus(a, '메인', ids.slice(1))).toThrowError(expect.objectContaining({ code: 'VALIDATION_ERROR' }))
    expect(() => be.reorderMenus(a, '없는카테고리', [])).toThrowError(expect.objectContaining({ code: 'NOT_FOUND' }))
  })

  it('이벤트를 구독자에게 전달한다 (주문 생성, 상태 변경, 삭제, 세션 종료)', () => {
    const events: ServerEvent[] = []
    be.subscribe((e) => events.push(e))
    const a = adminToken()
    const t = tableToken()
    const o = be.createOrder(t, orderBody([{ menuId: 1, quantity: 1 }]))
    be.changeOrderStatus(a, o.id, 'PREPARING')
    be.deleteOrder(a, o.id)
    be.createOrder(t, orderBody([{ menuId: 1, quantity: 1 }]))
    be.endSession(a, 1)
    expect(events.map((e) => e.type)).toEqual([
      'order_created',
      'order_status_changed',
      'order_deleted',
      'order_created',
      'session_ended',
    ])
    expect(events[0].tableId).toBe(1)
  })

  it('실패한 작업은 이벤트를 발행하지 않는다', () => {
    const events: ServerEvent[] = []
    be.subscribe((e) => events.push(e))
    const t = tableToken()
    expect(() =>
      be.createOrder(t, { clientOrderId: crypto.randomUUID(), items: [{ menuId: 1, quantity: 1 }], clientTotal: 1 }),
    ).toThrow()
    expect(events).toHaveLength(0)
  })

  it('storageKey를 지정하면 인스턴스 간에 상태를 공유한다', () => {
    const key = 'test.mock.store'
    const a = new MockBackend({ storageKey: key, now: () => clock })
    const b = new MockBackend({ storageKey: key, now: () => clock })
    const ta = a.customerLogin({ storeId: MOCK_STORE_ID, tableNumber: 1, password: MOCK_TABLE_PASSWORD }).accessToken
    const menus = a.getCustomerMenus(ta).flatMap((c) => c.menus)
    a.createOrder(ta, { clientOrderId: crypto.randomUUID(), items: [{ menuId: 6, quantity: 1 }], clientTotal: menus.find((m) => m.id === 6)!.price })
    const adminB = b.adminLogin({ storeId: MOCK_STORE_ID, username: MOCK_ADMIN_USERNAME, password: MOCK_ADMIN_PASSWORD }).accessToken
    expect(b.getDashboard(adminB, 1)[0].orderCount).toBe(1)
  })
})
