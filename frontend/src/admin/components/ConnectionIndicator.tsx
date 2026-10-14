import type { StreamStatus } from '../../shared/sse/useEventStream'
import styles from './ConnectionIndicator.module.css'

const LABEL: Record<StreamStatus, string> = {
  connecting: '실시간 연결 중...',
  open: '실시간 연결됨',
  reconnecting: '실시간 연결이 끊겨 다시 연결하는 중이에요',
}

export function ConnectionIndicator({ status }: { status: StreamStatus }) {
  const dotClass =
    status === 'open' ? styles.open : status === 'reconnecting' ? styles.reconnecting : styles.connecting
  return (
    <div className={styles.wrap} role="status" data-testid="connection-indicator" data-status={status}>
      <span className={`${styles.dot} ${dotClass}`} aria-hidden="true" />
      <span className={styles.label}>{LABEL[status]}</span>
    </div>
  )
}
