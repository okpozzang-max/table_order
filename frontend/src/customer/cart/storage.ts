import type { CartItem } from './cartReducer'

export const CART_STORAGE_KEY = 'tableorder.cart.v1'
export const PENDING_ORDER_KEY = 'tableorder.pendingOrder.v1'

interface StoredCart {
  tableKey: string
  items: CartItem[]
}

function isCartItem(v: unknown): v is CartItem {
  if (!v || typeof v !== 'object') return false
  const i = v as CartItem
  return (
    typeof i.menuId === 'number' &&
    typeof i.menuName === 'string' &&
    typeof i.unitPrice === 'number' &&
    typeof i.quantity === 'number'
  )
}

/**
 * 저장된 장바구니를 읽는다. tableKey가 현재 테이블과 다르면(또는 없음/깨짐) 빈 배열을 돌려주고
 * 오래된 저장분을 지운다.
 */
export function loadCart(currentTableKey: string | null): CartItem[] {
  const raw = localStorage.getItem(CART_STORAGE_KEY)
  if (!raw) return []
  try {
    const v = JSON.parse(raw) as unknown
    if (
      v &&
      typeof v === 'object' &&
      typeof (v as StoredCart).tableKey === 'string' &&
      Array.isArray((v as StoredCart).items) &&
      (v as StoredCart).items.every(isCartItem)
    ) {
      const stored = v as StoredCart
      if (currentTableKey && stored.tableKey === currentTableKey) return stored.items
    }
  } catch {
    // 무시: 아래에서 지운다
  }
  localStorage.removeItem(CART_STORAGE_KEY)
  return []
}

export function saveCart(currentTableKey: string | null, items: CartItem[]): void {
  if (!currentTableKey) return
  const payload: StoredCart = { tableKey: currentTableKey, items }
  localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(payload))
}

export function clearStoredCart(): void {
  localStorage.removeItem(CART_STORAGE_KEY)
}

export interface PendingOrder {
  clientOrderId: string
  cartSignature: string
}

export function readPendingOrder(): PendingOrder | null {
  const raw = localStorage.getItem(PENDING_ORDER_KEY)
  if (!raw) return null
  try {
    const v = JSON.parse(raw) as unknown
    if (
      v &&
      typeof v === 'object' &&
      typeof (v as PendingOrder).clientOrderId === 'string' &&
      typeof (v as PendingOrder).cartSignature === 'string'
    ) {
      return v as PendingOrder
    }
    return null
  } catch {
    return null
  }
}

export function writePendingOrder(p: PendingOrder): void {
  localStorage.setItem(PENDING_ORDER_KEY, JSON.stringify(p))
}

export function clearPendingOrder(): void {
  localStorage.removeItem(PENDING_ORDER_KEY)
}
