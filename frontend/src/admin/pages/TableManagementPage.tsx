import { useState } from 'react'
import { Button, ConfirmDialog, EmptyState, ErrorNotice, Spinner, useToast } from '../../shared/ui'
import { messageForError } from '../../shared/utils/errorMessages'
import { ApiError } from '../../shared/api/errors'
import type { TableInfo } from '../../shared/api/types'
import { useEndSession, useTables } from '../hooks/useAdminQueries'
import { TableRegisterForm } from '../components/TableRegisterForm'
import { TableHistoryModal } from '../components/TableHistoryModal'
import styles from './TableManagementPage.module.css'

export function TableManagementPage() {
  const toast = useToast()
  const tablesQuery = useTables()
  const endSession = useEndSession()

  const [historyTable, setHistoryTable] = useState<{ id: number; tableNumber: number } | null>(null)
  const [confirmTable, setConfirmTable] = useState<TableInfo | null>(null)

  const tables = tablesQuery.data ?? []

  const handleEndSession = () => {
    if (!confirmTable) return
    const table = confirmTable
    endSession.mutate(table.id, {
      onSuccess: () => {
        setConfirmTable(null)
        toast.success(`테이블 ${table.tableNumber} 이용을 완료했어요.`)
      },
      onError: (err) => {
        setConfirmTable(null)
        if (err instanceof ApiError && err.code === 'NO_ACTIVE_SESSION') {
          toast.error('이미 이용 완료된 테이블이에요.')
        } else {
          toast.error('이용 완료 처리에 실패했어요.')
        }
      },
    })
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>테이블 관리</h1>

      <div className={styles.layout}>
        <section className={styles.listSection}>
          {tablesQuery.isLoading ? <Spinner /> : null}
          {tablesQuery.isError ? (
            <ErrorNotice message={messageForError(tablesQuery.error)} data-testid="table-list-error" />
          ) : null}
          {!tablesQuery.isLoading && tables.length === 0 ? (
            <EmptyState message="등록된 테이블이 없어요" data-testid="table-list-empty" />
          ) : (
            <ul className={styles.list}>
              {tables.map((t) => (
                <li key={t.id} className={styles.row} data-testid={`table-list-row-${t.id}`}>
                  <span className={styles.number}>테이블 {t.tableNumber}</span>
                  <span className={styles.status} data-testid={`table-list-status-${t.id}`}>
                    {t.sessionActive ? '이용 중' : '비어 있음'}
                  </span>
                  <div className={styles.actions}>
                    <Button
                      onClick={() => setHistoryTable({ id: t.id, tableNumber: t.tableNumber })}
                      data-testid={`table-list-history-button-${t.id}`}
                    >
                      과거 내역
                    </Button>
                    <Button
                      variant="danger"
                      disabled={!t.sessionActive}
                      onClick={() => setConfirmTable(t)}
                      data-testid={`table-list-end-session-button-${t.id}`}
                    >
                      이용 완료
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <TableRegisterForm />
      </div>

      <ConfirmDialog
        open={confirmTable != null}
        title="이용 완료"
        message={
          confirmTable
            ? `테이블 ${confirmTable.tableNumber}의 이용을 완료할까요? 현재 주문은 과거 내역으로 이동하고 합계가 0원이 돼요.`
            : ''
        }
        confirmLabel="이용 완료"
        danger
        pending={endSession.isPending}
        onConfirm={handleEndSession}
        onCancel={() => setConfirmTable(null)}
        data-testid="table-management-end-session-confirm"
      />

      <TableHistoryModal table={historyTable} onClose={() => setHistoryTable(null)} />
    </div>
  )
}
