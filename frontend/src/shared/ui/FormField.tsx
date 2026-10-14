import { useId } from 'react'
import type { ReactNode } from 'react'
import styles from './FormField.module.css'

export interface FieldControlProps {
  id: string
  'aria-invalid': boolean
  'aria-describedby'?: string
}

export interface FormFieldProps {
  label: string
  error?: string
  hint?: string
  /** 입력 요소에 그대로 펼쳐 쓴다: `<input {...props} />` */
  children: (props: FieldControlProps) => ReactNode
  'data-testid'?: string
}

/** 라벨-입력-오류를 연결한다. 오류는 role="alert"로 즉시 읽힌다. */
export function FormField({ label, error, hint, children, 'data-testid': testId }: FormFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined

  return (
    <div className={styles.field} data-testid={testId}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': describedBy })}
      {hint ? (
        <div id={hintId} className={styles.hint}>
          {hint}
        </div>
      ) : null}
      {error ? (
        <div id={errorId} role="alert" className={styles.error} data-testid={testId ? `${testId}-error` : undefined}>
          {error}
        </div>
      ) : null}
    </div>
  )
}
