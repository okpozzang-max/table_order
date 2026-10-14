import { describe, expect, it } from 'vitest'
import {
  CART_STORAGE_KEY,
  PENDING_ORDER_KEY,
  clearPendingOrder,
  loadCart,
  readPendingOrder,
  saveCart,
  writePendingOrder,
} from './storage'
import type { CartItem } from './cartReducer'

const ITEMS: CartItem[] = [{ menuId: 1, menuName: '김치찌개', unitPrice: 9000, quantity: 2 }]

describe('cart storage', () => {
  it('saveCart then loadCart with same tableKey restores items', () => {
    saveCart('demo:3', ITEMS)
    expect(loadCart('demo:3')).toEqual(ITEMS)
  })

  it('loadCart discards and clears when tableKey differs', () => {
    saveCart('demo:3', ITEMS)
    expect(loadCart('demo:5')).toEqual([])
    expect(localStorage.getItem(CART_STORAGE_KEY)).toBeNull()
  })

  it('loadCart returns [] when nothing stored', () => {
    expect(loadCart('demo:1')).toEqual([])
  })

  it('loadCart handles corrupt data by clearing', () => {
    localStorage.setItem(CART_STORAGE_KEY, '{not json')
    expect(loadCart('demo:1')).toEqual([])
    expect(localStorage.getItem(CART_STORAGE_KEY)).toBeNull()
  })

  it('saveCart with null tableKey is a no-op', () => {
    saveCart(null, ITEMS)
    expect(localStorage.getItem(CART_STORAGE_KEY)).toBeNull()
  })
})

describe('pendingOrder storage', () => {
  it('write/read roundtrip', () => {
    writePendingOrder({ clientOrderId: 'abc', cartSignature: '1:2' })
    expect(readPendingOrder()).toEqual({ clientOrderId: 'abc', cartSignature: '1:2' })
  })

  it('clearPendingOrder removes the key', () => {
    writePendingOrder({ clientOrderId: 'abc', cartSignature: '1:2' })
    clearPendingOrder()
    expect(localStorage.getItem(PENDING_ORDER_KEY)).toBeNull()
    expect(readPendingOrder()).toBeNull()
  })

  it('readPendingOrder returns null on corrupt data', () => {
    localStorage.setItem(PENDING_ORDER_KEY, 'nope')
    expect(readPendingOrder()).toBeNull()
  })
})
