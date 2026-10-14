import { describe, expect, it } from 'vitest'
import type { Menu } from '../../shared/api/types'
import {
  cartReducer,
  cartTotalAmount,
  cartTotalCount,
  emptyCart,
} from './cartReducer'
import type { CartItem, CartState } from './cartReducer'

function menu(id: number, name: string, price: number): Menu {
  return { id, name, price, description: '', category: '메인', imageUrl: null, displayOrder: 1 }
}

function withItems(items: CartItem[]): CartState {
  return { items }
}

describe('cartReducer', () => {
  it('add: 새 메뉴는 수량 1로 추가된다', () => {
    const s = cartReducer(emptyCart, { type: 'add', menu: menu(1, '김치찌개', 9000) })
    expect(s.items).toEqual([{ menuId: 1, menuName: '김치찌개', unitPrice: 9000, quantity: 1 }])
  })

  it('add: 같은 메뉴를 다시 담으면 수량 +1', () => {
    let s = cartReducer(emptyCart, { type: 'add', menu: menu(1, '김치찌개', 9000) })
    s = cartReducer(s, { type: 'add', menu: menu(1, '김치찌개', 9000) })
    expect(s.items[0].quantity).toBe(2)
    expect(s.items).toHaveLength(1)
  })

  it('add: 20개에서 담기 시도는 상태를 바꾸지 않는다', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 20 }])
    const s1 = cartReducer(s0, { type: 'add', menu: menu(1, 'A', 1000) })
    expect(s1).toBe(s0)
    expect(s1.items[0].quantity).toBe(20)
  })

  it('increase: 20에서는 증가하지 않는다', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 20 }])
    const s1 = cartReducer(s0, { type: 'increase', menuId: 1 })
    expect(s1).toBe(s0)
  })

  it('increase: 20 미만이면 +1', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 5 }])
    const s1 = cartReducer(s0, { type: 'increase', menuId: 1 })
    expect(s1.items[0].quantity).toBe(6)
  })

  it('decrease: 수량 1에서 감소하면 항목 제거', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 1 }])
    const s1 = cartReducer(s0, { type: 'decrease', menuId: 1 })
    expect(s1.items).toHaveLength(0)
  })

  it('decrease: 수량 2 이상이면 -1', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 3 }])
    const s1 = cartReducer(s0, { type: 'decrease', menuId: 1 })
    expect(s1.items[0].quantity).toBe(2)
  })

  it('remove: 해당 항목만 제거', () => {
    const s0 = withItems([
      { menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 1 },
      { menuId: 2, menuName: 'B', unitPrice: 2000, quantity: 1 },
    ])
    const s1 = cartReducer(s0, { type: 'remove', menuId: 1 })
    expect(s1.items.map((i) => i.menuId)).toEqual([2])
  })

  it('removeMany: 여러 항목을 한 번에 제거', () => {
    const s0 = withItems([
      { menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 1 },
      { menuId: 2, menuName: 'B', unitPrice: 2000, quantity: 1 },
      { menuId: 3, menuName: 'C', unitPrice: 3000, quantity: 1 },
    ])
    const s1 = cartReducer(s0, { type: 'removeMany', menuIds: [1, 3] })
    expect(s1.items.map((i) => i.menuId)).toEqual([2])
  })

  it('clear: 모두 비운다', () => {
    const s0 = withItems([{ menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 1 }])
    expect(cartReducer(s0, { type: 'clear' }).items).toHaveLength(0)
  })

  it('refreshPrices: 매칭되는 항목의 단가만 갱신', () => {
    const s0 = withItems([
      { menuId: 1, menuName: 'A', unitPrice: 1000, quantity: 2 },
      { menuId: 2, menuName: 'B', unitPrice: 2000, quantity: 1 },
    ])
    const s1 = cartReducer(s0, { type: 'refreshPrices', prices: [{ menuId: 1, price: 1500 }] })
    expect(s1.items[0].unitPrice).toBe(1500)
    expect(s1.items[1].unitPrice).toBe(2000)
  })

  it('replace: 항목 교체', () => {
    const items = [{ menuId: 9, menuName: 'Z', unitPrice: 500, quantity: 4 }]
    expect(cartReducer(emptyCart, { type: 'replace', items }).items).toEqual(items)
  })
})

describe('cart totals', () => {
  it('totalAmount = sum(unitPrice*quantity)', () => {
    const items: CartItem[] = [
      { menuId: 1, menuName: 'A', unitPrice: 9000, quantity: 2 },
      { menuId: 2, menuName: 'B', unitPrice: 1000, quantity: 3 },
    ]
    expect(cartTotalAmount(items)).toBe(9000 * 2 + 1000 * 3)
    expect(cartTotalCount(items)).toBe(5)
  })
})
