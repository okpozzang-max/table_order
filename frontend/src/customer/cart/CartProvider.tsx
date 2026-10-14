import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react'
import type { ReactNode } from 'react'
import type { Menu } from '../../shared/api/types'
import { cartSignature } from '../../shared/utils/format'
import { MAX_CART_QUANTITY } from '../../shared/utils/validators'
import { readTableCredentials, tableKeyOf } from '../auth/storage'
import { cartReducer, cartTotalAmount, cartTotalCount, emptyCart } from './cartReducer'
import type { CartItem } from './cartReducer'
import { clearPendingOrder, loadCart, saveCart } from './storage'

export interface CartValue {
  items: CartItem[]
  totalAmount: number
  totalCount: number
  add(menu: Menu): 'added' | 'max'
  increase(menuId: number): 'ok' | 'max'
  decrease(menuId: number): void
  remove(menuId: number): void
  clear(): void
  refreshPrices(prices: { menuId: number; price: number }[]): void
  removeMany(menuIds: number[]): void
}

const CartContext = createContext<CartValue | null>(null)

export function CartProvider({ children }: { children: ReactNode }) {
  const tableKey = tableKeyOf(readTableCredentials())

  const [state, dispatch] = useReducer(cartReducer, undefined, () => ({
    items: loadCart(tableKey),
  }))

  // 서명 변화를 감지해서 pendingOrder를 지운다. 첫 렌더(복원) 서명은 기준으로만 쓰고 삭제하지 않는다.
  const lastSignature = useRef<string | null>(null)
  const hydrated = useRef(false)

  useEffect(() => {
    const sig = cartSignature(state.items)
    if (!hydrated.current) {
      hydrated.current = true
      lastSignature.current = sig
      // 복원 직후에는 저장만 한다(동일 내용 재저장은 무해).
      saveCart(tableKey, state.items)
      return
    }
    if (sig !== lastSignature.current) {
      lastSignature.current = sig
      clearPendingOrder()
    }
    saveCart(tableKey, state.items)
  }, [state.items, tableKey])

  const add = useCallback<CartValue['add']>((menu) => {
    const existing = state.items.find((i) => i.menuId === menu.id)
    if (existing && existing.quantity >= MAX_CART_QUANTITY) return 'max'
    dispatch({ type: 'add', menu })
    return 'added'
  }, [state.items])

  const increase = useCallback<CartValue['increase']>((menuId) => {
    const existing = state.items.find((i) => i.menuId === menuId)
    if (existing && existing.quantity >= MAX_CART_QUANTITY) return 'max'
    dispatch({ type: 'increase', menuId })
    return 'ok'
  }, [state.items])

  const decrease = useCallback<CartValue['decrease']>((menuId) => {
    dispatch({ type: 'decrease', menuId })
  }, [])

  const remove = useCallback<CartValue['remove']>((menuId) => {
    dispatch({ type: 'remove', menuId })
  }, [])

  const removeMany = useCallback<CartValue['removeMany']>((menuIds) => {
    dispatch({ type: 'removeMany', menuIds })
  }, [])

  const clear = useCallback<CartValue['clear']>(() => {
    dispatch({ type: 'clear' })
  }, [])

  const refreshPrices = useCallback<CartValue['refreshPrices']>((prices) => {
    dispatch({ type: 'refreshPrices', prices })
  }, [])

  const value = useMemo<CartValue>(
    () => ({
      items: state.items,
      totalAmount: cartTotalAmount(state.items),
      totalCount: cartTotalCount(state.items),
      add,
      increase,
      decrease,
      remove,
      removeMany,
      clear,
      refreshPrices,
    }),
    [state.items, add, increase, decrease, remove, removeMany, clear, refreshPrices],
  )

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('CartProvider 안에서만 useCart를 사용할 수 있어요.')
  return ctx
}

export { emptyCart }
