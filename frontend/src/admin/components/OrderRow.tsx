import { StatusBadge } from '../../shared/ui'
import { formatDateTime, formatKRW, summarizeItems } from '../../shared/utils/format'
import type { Order } from '../../shared/api/types'
import styles from './OrderRow.module.css'

export interface OrderRowProps {
  order: Order
  onClick: (order: Order) => void
}

export function OrderRow({ order, onClick }: OrderRowProps) {
  return (
    <button
      type="button"
      className={styles.row}
      onClick={() => onClick(order)}
      data-testid={`order-row-${order.id}`}
    >
      <span className={styles.number}>#{order.orderNumber}</span>
      <span className={styles.time}>{formatDateTime(order.createdAt)}</span>
      <span className={styles.summary}>{summarizeItems(order.items)}</span>
      <span className={styles.total}>{formatKRW(order.totalAmount)}</span>
      <StatusBadge status={order.status} />
    </button>
  )
}
