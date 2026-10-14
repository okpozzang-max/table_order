import type { Order } from '../../shared/api/types'
import { formatDateTime, formatKRW } from '../../shared/utils/format'
import { StatusBadge, Card } from '../../shared/ui'
import styles from './OrderListItem.module.css'

export function OrderListItem({ order }: { order: Order }) {
  return (
    <Card data-testid={`order-list-item-${order.id}`}>
      <div className={styles.head}>
        <span className={styles.number}>주문 #{order.orderNumber}</span>
        <StatusBadge status={order.status} />
      </div>
      <div className={styles.time}>{formatDateTime(order.createdAt)}</div>
      <ul className={styles.items}>
        {order.items.map((item) => (
          <li key={item.menuId} className={styles.item}>
            <span>
              {item.menuName} × {item.quantity}
            </span>
            <span>{formatKRW(item.unitPrice * item.quantity)}</span>
          </li>
        ))}
      </ul>
      <div className={styles.total}>
        <span>합계</span>
        <strong data-testid={`order-list-item-total-${order.id}`}>{formatKRW(order.totalAmount)}</strong>
      </div>
    </Card>
  )
}
