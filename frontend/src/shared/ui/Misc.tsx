import type { ReactNode } from 'react'
import styles from './Misc.module.css'

export function Spinner({ label = '불러오는 중...' }: { label?: string }) {
  return (
    <div className={styles.spinnerWrap} role="status" data-testid="spinner">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ message, 'data-testid': testId = 'empty-state' }: { message: string; 'data-testid'?: string }) {
  return (
    <div className={styles.empty} data-testid={testId}>
      {message}
    </div>
  )
}

export function Card({
  children,
  className,
  highlighted = false,
  'data-testid': testId,
}: {
  children: ReactNode
  className?: string
  highlighted?: boolean
  'data-testid'?: string
}) {
  const classes = [styles.card, highlighted ? styles.highlighted : '', className].filter(Boolean).join(' ')
  return (
    <section className={classes} data-testid={testId} data-highlighted={highlighted ? 'true' : undefined}>
      {children}
    </section>
  )
}

/** 인라인 오류 박스 (role="alert") */
export function ErrorNotice({ message, 'data-testid': testId = 'error-notice' }: { message: string; 'data-testid'?: string }) {
  return (
    <div role="alert" className={styles.errorNotice} data-testid={testId}>
      {message}
    </div>
  )
}
