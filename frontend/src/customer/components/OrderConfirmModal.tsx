import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../shared/api/errors'
import type { OrderCreateRequest } from '../../shared/api/types'
import { cartSignature, formatKRW } from '../../shared/utils/format'
import { messageForError, ORDER_ERROR_MESSAGES } from '../../shared/utils/errorMessages'
import { Button, Modal } from '../../shared/ui'
import { useCart } from '../cart/CartProvider'
import { useCreateOrder } from '../hooks/useCreateOrder'
import { MENUS_QUERY_KEY } from '../hooks/useMenus'
import { clearPendingOrder, readPendingOrder, writePendingOrder } from '../cart/storage'
import styles from './OrderConfirmModal.module.css'

export interface OrderConfirmModalProps {
  open: boolean
  onClose(): void
}

type SpecialError =
  | { kind: 'price_changed'; message: string; prices: { menuId: number; price: number }[] }
  | { kind: 'menu_unavailable'; message: string; menuIds: number[] }
  | { kind: 'generic'; message: string }
  | null

/** 장바구니 서명에 맞는 clientOrderId를 결정한다. 같은 서명이면 재사용, 아니면 새 UUID. */
function resolveClientOrderId(signature: string): string {
  const pending = readPendingOrder()
  if (pending && pending.cartSignature === signature) return pending.clientOrderId
  const id = crypto.randomUUID()
  writePendingOrder({ clientOrderId: id, cartSignature: signature })
  return id
}

export function OrderConfirmModal({ open, onClose }: OrderConfirmModalProps) {
  const cart = useCart()
  const createOrder = useCreateOrder()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [error, setError] = useState<SpecialError>(null)
  const clientOrderIdRef = useRef<string | null>(null)

  // 모달이 열릴 때 clientOrderId를 확정하고 오류를 초기화한다.
  useEffect(() => {
    if (open) {
      clientOrderIdRef.current = resolveClientOrderId(cartSignature(cart.items))
      setError(null)
    }
    // open 변화에만 반응한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const submit = useCallback(async () => {
    const clientOrderId = clientOrderIdRef.current ?? resolveClientOrderId(cartSignature(cart.items))
    clientOrderIdRef.current = clientOrderId
    const req: OrderCreateRequest = {
      clientOrderId,
      items: cart.items.map((i) => ({ menuId: i.menuId, quantity: i.quantity })),
      clientTotal: cart.totalAmount,
    }
    setError(null)
    try {
      const order = await createOrder.mutateAsync(req)
      clearPendingOrder()
      cart.clear()
      navigate('/customer/order-complete', { state: { orderNumber: order.orderNumber } })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'PRICE_CHANGED') {
        setError({
          kind: 'price_changed',
          message: messageForError(err, ORDER_ERROR_MESSAGES),
          prices: err.body?.details?.currentPrices ?? [],
        })
        return
      }
      if (err instanceof ApiError && err.code === 'MENU_UNAVAILABLE') {
        setError({
          kind: 'menu_unavailable',
          message: messageForError(err, ORDER_ERROR_MESSAGES),
          menuIds: err.body?.details?.menuIds ?? [],
        })
        return
      }
      setError({ kind: 'generic', message: messageForError(err, ORDER_ERROR_MESSAGES) })
    }
  }, [cart, createOrder, navigate])

  const handleRefreshPrices = useCallback(
    (prices: { menuId: number; price: number }[]) => {
      cart.refreshPrices(prices)
      // 갱신 후의 장바구니 서명으로 새 clientOrderId를 만든다 (수량은 그대로, 단가만 바뀜 -> 서명은 동일하지만 명시적으로 재발급).
      const sig = cartSignature(cart.items.map((i) => ({ menuId: i.menuId, quantity: i.quantity })))
      const id = crypto.randomUUID()
      writePendingOrder({ clientOrderId: id, cartSignature: sig })
      clientOrderIdRef.current = id
      void queryClient.invalidateQueries({ queryKey: MENUS_QUERY_KEY })
      setError(null)
    },
    [cart, queryClient],
  )

  const handleRemoveUnavailable = useCallback(
    (menuIds: number[]) => {
      cart.removeMany(menuIds)
      const remaining = cart.items.filter((i) => !menuIds.includes(i.menuId))
      setError(null)
      if (remaining.length > 0) {
        // 남은 항목이 있으면 사용자가 다시 확인하도록 모달을 닫는다.
        onClose()
      }
    },
    [cart, onClose],
  )

  const pending = createOrder.isPending

  const unavailableNames =
    error?.kind === 'menu_unavailable'
      ? cart.items.filter((i) => error.menuIds.includes(i.menuId)).map((i) => i.menuName)
      : []

  const footer = (
    <>
      <Button
        variant="ghost"
        onClick={onClose}
        disabled={pending}
        data-testid="order-confirm-cancel-button"
      >
        취소
      </Button>
      <Button
        variant="primary"
        onClick={() => void submit()}
        loading={pending}
        data-testid="order-confirm-submit-button"
      >
        주문 확정
      </Button>
    </>
  )

  return (
    <Modal
      open={open}
      title="주문 확인"
      onClose={onClose}
      dismissible={!pending}
      footer={footer}
      data-testid="order-confirm-modal"
    >
      <ul className={styles.list}>
        {cart.items.map((item) => (
          <li key={item.menuId} className={styles.row} data-testid={`order-confirm-item-${item.menuId}`}>
            <span className={styles.name}>{item.menuName}</span>
            <span className={styles.qty}>
              {formatKRW(item.unitPrice)} × {item.quantity}
            </span>
            <span className={styles.subtotal}>{formatKRW(item.unitPrice * item.quantity)}</span>
          </li>
        ))}
      </ul>
      <div className={styles.total}>
        <span>총 금액</span>
        <strong data-testid="order-confirm-total">{formatKRW(cart.totalAmount)}</strong>
      </div>

      {error ? (
        <div role="alert" className={styles.error} data-testid="order-confirm-error">
          <p className={styles.errorMessage}>{error.message}</p>
          {error.kind === 'menu_unavailable' && unavailableNames.length > 0 ? (
            <p className={styles.unavailable} data-testid="order-confirm-unavailable-names">
              판매하지 않는 메뉴: {unavailableNames.join(', ')}
            </p>
          ) : null}

          {error.kind === 'price_changed' ? (
            <Button
              variant="primary"
              onClick={() => handleRefreshPrices(error.prices)}
              data-testid="order-confirm-refresh-prices-button"
            >
              최신 가격으로 갱신
            </Button>
          ) : null}
          {error.kind === 'menu_unavailable' ? (
            <Button
              variant="primary"
              onClick={() => handleRemoveUnavailable(error.menuIds)}
              data-testid="order-confirm-remove-unavailable-button"
            >
              해당 메뉴 제거
            </Button>
          ) : null}
        </div>
      ) : null}
    </Modal>
  )
}
