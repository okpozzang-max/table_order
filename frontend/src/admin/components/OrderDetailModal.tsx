import { useState } from 'react'
import { Button, ConfirmDialog, ErrorNotice, Modal, Spinner, StatusBadge, useToast } from '../../shared/ui'
import { formatDateTime, formatKRW } from '../../shared/utils/format'
import { messageForError } from '../../shared/utils/errorMessages'
import { ApiError } from '../../shared/api/errors'
import { NEXT_ACTION_LABEL, NEXT_ORDER_STATUS } from '../../shared/api/types'
import { useChangeOrderStatus, useDeleteOrder, useOrderDetail } from '../hooks/useAdminQueries'
import styles from './OrderDetailModal.module.css'

export interface OrderDetailModalProps {
  orderId: number | null
  onClose: () => void
}

export function OrderDetailModal({ orderId, onClose }: OrderDetailModalProps) {
  const toast = useToast()
  const query = useOrderDetail(orderId)
  const changeStatus = useChangeOrderStatus()
  const deleteOrder = useDeleteOrder()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const order = query.data

  const handleNextStep = () => {
    if (!order) return
    const next = NEXT_ORDER_STATUS[order.status]
    if (!next) return
    changeStatus.mutate(
      { orderId: order.id, status: next },
      {
        onError: (err) => {
          if (err instanceof ApiError && err.code === 'INVALID_TRANSITION') {
            toast.error(messageForError(err))
            void query.refetch()
          } else {
            toast.error(messageForError(err))
          }
        },
      },
    )
  }

  const handleDelete = () => {
    if (!order) return
    deleteOrder.mutate(order.id, {
      onSuccess: () => {
        setConfirmOpen(false)
        toast.success('주문을 삭제했어요.')
        onClose()
      },
      onError: (err) => {
        setConfirmOpen(false)
        if (err instanceof ApiError && err.code === 'NOT_FOUND') {
          toast.error('이미 삭제된 주문이에요.')
          onClose()
        } else {
          toast.error('주문을 삭제하지 못했어요. 다시 시도해주세요.')
        }
      },
    })
  }

  const nextLabel = order ? NEXT_ACTION_LABEL[order.status] : null

  return (
    <>
      <Modal
        open={orderId != null && !confirmOpen}
        title={order ? `주문 #${order.orderNumber}` : '주문 상세'}
        onClose={onClose}
        data-testid="order-detail-modal"
        footer={
          order ? (
            <>
              {nextLabel ? (
                <Button
                  variant="primary"
                  loading={changeStatus.isPending}
                  onClick={handleNextStep}
                  data-testid="order-detail-next-step-button"
                >
                  {nextLabel}
                </Button>
              ) : null}
              <Button
                variant="danger"
                onClick={() => setConfirmOpen(true)}
                data-testid="order-detail-delete-button"
              >
                삭제
              </Button>
            </>
          ) : null
        }
      >
        {query.isLoading ? <Spinner /> : null}
        {query.isError ? (
          <div>
            <ErrorNotice message={messageForError(query.error)} data-testid="order-detail-error" />
            <Button onClick={() => void query.refetch()} data-testid="order-detail-retry-button">
              다시 시도
            </Button>
          </div>
        ) : null}
        {order ? (
          <div className={styles.body}>
            <div className={styles.meta}>
              <span>테이블 {order.tableNumber}</span>
              <span>{formatDateTime(order.createdAt)}</span>
              <StatusBadge status={order.status} />
            </div>
            <table className={styles.items}>
              <thead>
                <tr>
                  <th>메뉴</th>
                  <th>수량</th>
                  <th>단가</th>
                  <th>소계</th>
                </tr>
              </thead>
              <tbody>
                {order.items.map((it) => (
                  <tr key={it.menuId} data-testid={`order-detail-item-${it.menuId}`}>
                    <td>{it.menuName}</td>
                    <td>{it.quantity}</td>
                    <td>{formatKRW(it.unitPrice)}</td>
                    <td>{formatKRW(it.unitPrice * it.quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className={styles.total} data-testid="order-detail-total">
              합계 {formatKRW(order.totalAmount)}
            </div>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={confirmOpen}
        title="주문 삭제"
        message={
          order
            ? `주문 ${order.orderNumber}를 삭제할까요? 삭제하면 테이블 총 주문액이 다시 계산돼요.`
            : ''
        }
        confirmLabel="삭제"
        danger
        pending={deleteOrder.isPending}
        onConfirm={handleDelete}
        onCancel={() => setConfirmOpen(false)}
        data-testid="order-detail-delete-confirm"
      />
    </>
  )
}
