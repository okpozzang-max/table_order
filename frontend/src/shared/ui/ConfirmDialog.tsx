import { Button } from './Button'
import { Modal } from './Modal'

export interface ConfirmDialogProps {
  open: boolean
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  /** 처리 중: 확인 버튼 비활성 + 로딩 표시, 닫기 불가 */
  pending?: boolean
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
  'data-testid'?: string
}

export function ConfirmDialog({
  open,
  title = '확인',
  message,
  confirmLabel = '확인',
  cancelLabel = '취소',
  pending = false,
  danger = false,
  onConfirm,
  onCancel,
  'data-testid': testId = 'confirm-dialog',
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onCancel}
      dismissible={!pending}
      size="sm"
      data-testid={testId}
      footer={
        <>
          <Button onClick={onCancel} disabled={pending} data-testid={`${testId}-cancel-button`}>
            {cancelLabel}
          </Button>
          <Button
            variant={danger ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={pending}
            data-testid={`${testId}-confirm-button`}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  )
}
