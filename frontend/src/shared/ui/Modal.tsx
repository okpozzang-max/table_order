import { useEffect, useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import styles from './Modal.module.css'

export interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  /** 하단 버튼 영역 */
  footer?: ReactNode
  /** 닫기(Esc/배경 클릭)를 막고 싶을 때 (처리 중 등) */
  dismissible?: boolean
  size?: 'sm' | 'md' | 'lg'
  'data-testid'?: string
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** 접근성: role=dialog, 포커스 트랩, Esc 닫기, 배경 클릭 닫기 */
export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  dismissible = true,
  size = 'md',
  'data-testid': testId,
}: ModalProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previouslyFocused.current = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current
    const first = dialog?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? dialog)?.focus()
    return () => {
      previouslyFocused.current?.focus?.()
    }
  }, [open])

  if (!open) return null

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' && dismissible) {
      e.stopPropagation()
      onClose()
      return
    }
    if (e.key !== 'Tab') return
    const dialog = dialogRef.current
    if (!dialog) return
    const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (items.length === 0) {
      e.preventDefault()
      return
    }
    const firstEl = items[0]
    const lastEl = items[items.length - 1]
    if (e.shiftKey && document.activeElement === firstEl) {
      e.preventDefault()
      lastEl.focus()
    } else if (!e.shiftKey && document.activeElement === lastEl) {
      e.preventDefault()
      firstEl.focus()
    }
  }

  return createPortal(
    <div
      className={styles.backdrop}
      data-testid={testId ? `${testId}-backdrop` : undefined}
      onMouseDown={(e) => {
        if (dismissible && e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={dialogRef}
        className={`${styles.dialog} ${styles[size]}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        data-testid={testId}
      >
        <div className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
        </div>
        <div className={styles.body}>{children}</div>
        {footer ? <div className={styles.footer}>{footer}</div> : null}
      </div>
    </div>,
    document.body,
  )
}
