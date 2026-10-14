import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  /** true이면 비활성화되고 진행 중 표시. 클릭은 무시된다. */
  loading?: boolean
}

export function Button({
  variant = 'secondary',
  loading = false,
  disabled,
  className,
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  const classes = [styles.button, styles[variant], className].filter(Boolean).join(' ')
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className={styles.spinner} aria-hidden="true" /> : null}
      {children}
    </button>
  )
}
