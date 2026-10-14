import { ORDER_STATUS_LABEL } from '../api/types'
import type { OrderStatus } from '../api/types'
import styles from './StatusBadge.module.css'

const CLASS_BY_STATUS: Record<OrderStatus, string> = {
  PENDING: styles.pending,
  PREPARING: styles.preparing,
  COMPLETED: styles.completed,
}

/** 색뿐 아니라 텍스트로도 상태를 표시한다. */
export function StatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`${styles.badge} ${CLASS_BY_STATUS[status]}`} data-testid={`status-badge-${status}`}>
      {ORDER_STATUS_LABEL[status]}
    </span>
  )
}
