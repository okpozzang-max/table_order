import { useState } from 'react'
import { Button, ErrorNotice, Spinner } from '../../shared/ui'
import { messageForError } from '../../shared/utils/errorMessages'
import type { Order } from '../../shared/api/types'
import { useDashboard, useTables } from '../hooks/useAdminQueries'
import { useAdminRealtime } from '../realtime/AdminRealtimeProvider'
import { TableCard } from '../components/TableCard'
import { OrderDetailModal } from '../components/OrderDetailModal'
import { TableHistoryModal } from '../components/TableHistoryModal'
import styles from './DashboardPage.module.css'

export function DashboardPage() {
  const [tableFilter, setTableFilter] = useState<number | null>(null)
  const [detailOrderId, setDetailOrderId] = useState<number | null>(null)
  const [historyTable, setHistoryTable] = useState<{ id: number; tableNumber: number } | null>(null)

  const { unseen, markSeen } = useAdminRealtime()
  const tablesQuery = useTables()
  const dashboardQuery = useDashboard(tableFilter)

  const summaries = dashboardQuery.data ?? []
  const tables = tablesQuery.data ?? []

  const handleOrderClick = (order: Order) => {
    markSeen(order.tableId)
    setDetailOrderId(order.id)
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>대시보드</h1>
        <label className={styles.filter}>
          테이블
          <select
            className={styles.select}
            value={tableFilter ?? 'all'}
            onChange={(e) => setTableFilter(e.target.value === 'all' ? null : Number(e.target.value))}
            data-testid="dashboard-table-filter"
          >
            <option value="all">전체</option>
            {tables.map((t) => (
              <option key={t.id} value={t.tableNumber}>
                테이블 {t.tableNumber}
              </option>
            ))}
          </select>
        </label>
      </header>

      {dashboardQuery.isLoading ? <Spinner /> : null}
      {dashboardQuery.isError ? (
        <div>
          <ErrorNotice message={messageForError(dashboardQuery.error)} data-testid="dashboard-error" />
          <Button onClick={() => void dashboardQuery.refetch()} data-testid="dashboard-retry-button">
            다시 시도
          </Button>
        </div>
      ) : null}

      <div className={styles.grid}>
        {summaries.map((summary) => (
          <TableCard
            key={summary.tableId}
            summary={summary}
            highlighted={(unseen[summary.tableId]?.length ?? 0) > 0}
            filtered={tableFilter != null}
            onHeaderClick={markSeen}
            onOrderClick={handleOrderClick}
            onViewAll={(tableId) => {
              const s = summaries.find((x) => x.tableId === tableId)
              if (s) setTableFilter(s.tableNumber)
            }}
            onClearFilter={() => setTableFilter(null)}
            onOpenHistory={setHistoryTable}
          />
        ))}
      </div>

      <OrderDetailModal orderId={detailOrderId} onClose={() => setDetailOrderId(null)} />
      <TableHistoryModal table={historyTable} onClose={() => setHistoryTable(null)} />
    </div>
  )
}
