import { useMemo, useState } from 'react'
import { Button, EmptyState, ErrorNotice, FormField, Modal, Spinner } from '../../shared/ui'
import { formatDateTime, formatKRW, summarizeItems } from '../../shared/utils/format'
import { messageForError } from '../../shared/utils/errorMessages'
import { validateDateRange } from '../../shared/utils/validators'
import { useTableHistory } from '../hooks/useAdminQueries'
import styles from './TableHistoryModal.module.css'

export interface TableHistoryModalProps {
  table: { id: number; tableNumber: number } | null
  onClose: () => void
}

export function TableHistoryModal({ table, onClose }: TableHistoryModalProps) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const rangeErrors = useMemo(() => validateDateRange(from, to), [from, to])
  const rangeValid = Object.keys(rangeErrors).length === 0

  const query = useTableHistory(
    table?.id ?? null,
    { from: from || undefined, to: to || undefined },
    { enabled: table != null && rangeValid },
  )

  const history = query.data ?? []

  return (
    <Modal
      open={table != null}
      title={table ? `테이블 ${table.tableNumber} 과거 내역` : '과거 내역'}
      onClose={onClose}
      size="lg"
      data-testid="table-history-modal"
      footer={
        <Button onClick={onClose} data-testid="table-history-close-button">
          닫기
        </Button>
      }
    >
      <div className={styles.filters}>
        <FormField label="시작일" data-testid="table-history-from-field">
          {(p) => (
            <input
              {...p}
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className={styles.input}
              data-testid="table-history-from-input"
            />
          )}
        </FormField>
        <FormField
          label="종료일"
          error={rangeErrors.to}
          data-testid="table-history-to-field"
        >
          {(p) => (
            <input
              {...p}
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className={styles.input}
              data-testid="table-history-to-input"
            />
          )}
        </FormField>
      </div>

      {query.isLoading && rangeValid ? <Spinner /> : null}
      {query.isError ? (
        <ErrorNotice message={messageForError(query.error)} data-testid="table-history-error" />
      ) : null}

      {rangeValid && !query.isLoading && !query.isError ? (
        history.length === 0 ? (
          <EmptyState message="과거 내역이 없어요" data-testid="table-history-empty" />
        ) : (
          <ul className={styles.list}>
            {history.map((h) => (
              <li key={h.orderId} className={styles.item} data-testid={`table-history-row-${h.orderId}`}>
                <div className={styles.rowTop}>
                  <span className={styles.number}>#{h.orderNumber}</span>
                  <span className={styles.time}>{formatDateTime(h.createdAt)}</span>
                </div>
                <div className={styles.summary}>{summarizeItems(h.items)}</div>
                <div className={styles.rowBottom}>
                  <span className={styles.total}>{formatKRW(h.totalAmount)}</span>
                  <span className={styles.completed}>
                    이용 완료 시각 {formatDateTime(h.completedAt)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </Modal>
  )
}
