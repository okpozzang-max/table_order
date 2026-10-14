import { useState } from 'react'
import { Button, Card, ConfirmDialog, EmptyState, useToast } from '../../shared/ui'
import { formatKRW } from '../../shared/utils/format'
import { ApiError } from '../../shared/api/errors'
import type { Order, TableSummary } from '../../shared/api/types'
import { useEndSession } from '../hooks/useAdminQueries'
import { OrderRow } from './OrderRow'
import styles from './TableCard.module.css'

export interface TableCardProps {
  summary: TableSummary
  highlighted: boolean
  /** 테이블 단위 필터 적용 여부 (true이면 전체 주문을 보여주는 중) */
  filtered: boolean
  onHeaderClick: (tableId: number) => void
  onOrderClick: (order: Order) => void
  onViewAll: (tableId: number) => void
  onClearFilter: () => void
  onOpenHistory: (table: { id: number; tableNumber: number }) => void
}

export function TableCard({
  summary,
  highlighted,
  filtered,
  onHeaderClick,
  onOrderClick,
  onViewAll,
  onClearFilter,
  onOpenHistory,
}: TableCardProps) {
  const toast = useToast()
  const endSession = useEndSession()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const handleEndSession = () => {
    endSession.mutate(summary.tableId, {
      onSuccess: () => {
        setConfirmOpen(false)
        toast.success(`테이블 ${summary.tableNumber} 이용을 완료했어요.`)
      },
      onError: (err) => {
        setConfirmOpen(false)
        if (err instanceof ApiError && err.code === 'NO_ACTIVE_SESSION') {
          toast.error('이미 이용 완료된 테이블이에요.')
        } else {
          toast.error('이용 완료 처리에 실패했어요.')
        }
      },
    })
  }

  return (
    <Card highlighted={highlighted} data-testid={`table-card-${summary.tableId}`}>
      <button
        type="button"
        className={styles.header}
        onClick={() => onHeaderClick(summary.tableId)}
        data-testid={`table-card-header-${summary.tableId}`}
      >
        <h3 className={styles.title}>테이블 {summary.tableNumber}</h3>
        <div className={styles.meta}>
          <span data-testid={`table-card-total-${summary.tableId}`}>
            총 주문액 {formatKRW(summary.totalAmount)}
          </span>
          <span data-testid={`table-card-count-${summary.tableId}`}>
            주문 {summary.orderCount}개
          </span>
        </div>
      </button>

      <div className={styles.orders}>
        {summary.orders.length === 0 ? (
          <EmptyState message="주문이 없어요" data-testid={`table-card-empty-${summary.tableId}`} />
        ) : (
          summary.orders.map((o) => <OrderRow key={o.id} order={o} onClick={onOrderClick} />)
        )}
      </div>

      <div className={styles.actions}>
        {filtered ? (
          <Button
            onClick={onClearFilter}
            data-testid={`table-card-clear-filter-button-${summary.tableId}`}
          >
            전체 목록으로
          </Button>
        ) : (
          <Button
            onClick={() => onViewAll(summary.tableId)}
            data-testid={`table-card-view-all-button-${summary.tableId}`}
          >
            전체 보기
          </Button>
        )}
        <Button
          onClick={() => onOpenHistory({ id: summary.tableId, tableNumber: summary.tableNumber })}
          data-testid={`table-card-history-button-${summary.tableId}`}
        >
          과거 내역
        </Button>
        <Button
          variant="danger"
          disabled={!summary.sessionActive}
          onClick={() => setConfirmOpen(true)}
          data-testid={`table-card-end-session-button-${summary.tableId}`}
        >
          이용 완료
        </Button>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="이용 완료"
        message={`테이블 ${summary.tableNumber}의 이용을 완료할까요? 현재 주문은 과거 내역으로 이동하고 합계가 0원이 돼요.`}
        confirmLabel="이용 완료"
        danger
        pending={endSession.isPending}
        onConfirm={handleEndSession}
        onCancel={() => setConfirmOpen(false)}
        data-testid={`table-card-end-session-confirm-${summary.tableId}`}
      />
    </Card>
  )
}
