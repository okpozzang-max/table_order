import { formatKRW } from '../../shared/utils/format'
import { MAX_CART_QUANTITY } from '../../shared/utils/validators'
import { Button, EmptyState } from '../../shared/ui'
import { useCart } from '../cart/CartProvider'
import styles from './CartPanel.module.css'

export interface CartPanelProps {
  onOrder(): void
  onIncreaseBlocked?(): void
}

export function CartPanel({ onOrder, onIncreaseBlocked }: CartPanelProps) {
  const cart = useCart()
  const empty = cart.items.length === 0

  const handleIncrease = (menuId: number) => {
    const r = cart.increase(menuId)
    if (r === 'max') onIncreaseBlocked?.()
  }

  return (
    <aside className={styles.panel} aria-label="장바구니" data-testid="cart-panel">
      <h2 className={styles.title}>장바구니</h2>
      {empty ? (
        <EmptyState message="담은 메뉴가 없어요" data-testid="cart-panel-empty" />
      ) : (
        <ul className={styles.list}>
          {cart.items.map((item) => {
            const atMax = item.quantity >= MAX_CART_QUANTITY
            return (
              <li key={item.menuId} className={styles.item} data-testid={`cart-panel-item-${item.menuId}`}>
                <div className={styles.itemHead}>
                  <span className={styles.itemName}>{item.menuName}</span>
                  <button
                    type="button"
                    className={styles.removeBtn}
                    onClick={() => cart.remove(item.menuId)}
                    aria-label={`${item.menuName} 삭제`}
                    data-testid={`cart-panel-remove-button-${item.menuId}`}
                  >
                    삭제
                  </button>
                </div>
                <div className={styles.itemControls}>
                  <div className={styles.qtyGroup}>
                    <button
                      type="button"
                      className={styles.qtyBtn}
                      onClick={() => cart.decrease(item.menuId)}
                      aria-label={`${item.menuName} 수량 감소`}
                      data-testid={`cart-panel-decrease-button-${item.menuId}`}
                    >
                      −
                    </button>
                    <span className={styles.qty} data-testid={`cart-panel-quantity-${item.menuId}`}>
                      {item.quantity}
                    </span>
                    <button
                      type="button"
                      className={styles.qtyBtn}
                      onClick={() => handleIncrease(item.menuId)}
                      disabled={atMax}
                      aria-label={`${item.menuName} 수량 증가`}
                      data-testid={`cart-panel-increase-button-${item.menuId}`}
                    >
                      +
                    </button>
                  </div>
                  <span className={styles.subtotal} data-testid={`cart-panel-subtotal-${item.menuId}`}>
                    {formatKRW(item.unitPrice * item.quantity)}
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <div className={styles.totalRow}>
        <span>합계</span>
        <strong data-testid="cart-panel-total">{formatKRW(cart.totalAmount)}</strong>
      </div>

      <div className={styles.actions}>
        <Button
          variant="ghost"
          onClick={cart.clear}
          disabled={empty}
          data-testid="cart-panel-clear-button"
        >
          비우기
        </Button>
        <Button
          variant="primary"
          onClick={onOrder}
          disabled={empty}
          data-testid="cart-panel-order-button"
        >
          주문하기
        </Button>
      </div>
    </aside>
  )
}
