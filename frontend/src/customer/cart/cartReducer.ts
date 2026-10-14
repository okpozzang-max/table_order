import type { Menu } from '../../shared/api/types'
import { MAX_CART_QUANTITY } from '../../shared/utils/validators'

export interface CartItem {
  menuId: number
  menuName: string
  unitPrice: number
  quantity: number
}

export interface CartState {
  items: CartItem[]
}

export const emptyCart: CartState = { items: [] }

export type CartAction =
  | { type: 'add'; menu: Menu }
  | { type: 'increase'; menuId: number }
  | { type: 'decrease'; menuId: number }
  | { type: 'remove'; menuId: number }
  | { type: 'removeMany'; menuIds: number[] }
  | { type: 'clear' }
  | { type: 'refreshPrices'; prices: { menuId: number; price: number }[] }
  | { type: 'replace'; items: CartItem[] }

export function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add': {
      const existing = state.items.find((i) => i.menuId === action.menu.id)
      if (existing) {
        if (existing.quantity >= MAX_CART_QUANTITY) return state
        return {
          items: state.items.map((i) =>
            i.menuId === action.menu.id ? { ...i, quantity: i.quantity + 1 } : i,
          ),
        }
      }
      const item: CartItem = {
        menuId: action.menu.id,
        menuName: action.menu.name,
        unitPrice: action.menu.price,
        quantity: 1,
      }
      return { items: [...state.items, item] }
    }
    case 'increase': {
      const existing = state.items.find((i) => i.menuId === action.menuId)
      if (!existing || existing.quantity >= MAX_CART_QUANTITY) return state
      return {
        items: state.items.map((i) =>
          i.menuId === action.menuId ? { ...i, quantity: i.quantity + 1 } : i,
        ),
      }
    }
    case 'decrease': {
      const existing = state.items.find((i) => i.menuId === action.menuId)
      if (!existing) return state
      if (existing.quantity <= 1) {
        return { items: state.items.filter((i) => i.menuId !== action.menuId) }
      }
      return {
        items: state.items.map((i) =>
          i.menuId === action.menuId ? { ...i, quantity: i.quantity - 1 } : i,
        ),
      }
    }
    case 'remove':
      return { items: state.items.filter((i) => i.menuId !== action.menuId) }
    case 'removeMany': {
      const ids = new Set(action.menuIds)
      return { items: state.items.filter((i) => !ids.has(i.menuId)) }
    }
    case 'clear':
      return emptyCart
    case 'refreshPrices': {
      const map = new Map(action.prices.map((p) => [p.menuId, p.price]))
      return {
        items: state.items.map((i) =>
          map.has(i.menuId) ? { ...i, unitPrice: map.get(i.menuId) as number } : i,
        ),
      }
    }
    case 'replace':
      return { items: action.items }
    default:
      return state
  }
}

export function cartTotalAmount(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + i.unitPrice * i.quantity, 0)
}

export function cartTotalCount(items: CartItem[]): number {
  return items.reduce((sum, i) => sum + i.quantity, 0)
}
