import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, ErrorNotice, FormField } from '../../shared/ui'
import { validateAdminLogin } from '../../shared/utils/validators'
import type { FieldErrors } from '../../shared/utils/validators'
import {
  ADMIN_LOGIN_ERROR_MESSAGES,
  lockedMessage,
  messageForError,
} from '../../shared/utils/errorMessages'
import { ApiError } from '../../shared/api/errors'
import { useAdminAuth } from '../auth/AdminAuthProvider'
import styles from './LoginPage.module.css'

interface LocationState {
  from?: string
}

export function LoginPage() {
  const { login, isAuthenticated, sessionExpired } = useAdminAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [storeId, setStoreId] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [lockRemaining, setLockRemaining] = useState(0)
  const lockTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (lockTimer.current) clearInterval(lockTimer.current)
    }
  }, [])

  // 로그인 직후(또는 이미 인증된 상태)에는 보호 경로로 접근했던 원래 경로로 돌려보낸다.
  const from = (location.state as LocationState | null)?.from ?? '/admin/dashboard'
  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  const startLockCountdown = (seconds: number) => {
    setLockRemaining(seconds)
    if (lockTimer.current) clearInterval(lockTimer.current)
    lockTimer.current = setInterval(() => {
      setLockRemaining((prev) => {
        if (prev <= 1) {
          if (lockTimer.current) clearInterval(lockTimer.current)
          lockTimer.current = null
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (lockRemaining > 0) return
    const result = validateAdminLogin({ storeId, username, password })
    if (!result.value) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    setFormError(null)
    setSubmitting(true)
    try {
      await login(result.value.storeId, result.value.username, result.value.password)
      navigate(from, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'ACCOUNT_LOCKED') {
        const seconds = err.retryAfterSeconds ?? 0
        startLockCountdown(seconds)
        setFormError(lockedMessage(seconds))
      } else if (err instanceof ApiError && err.code === 'INVALID_CREDENTIALS') {
        setFormError(messageForError(err, ADMIN_LOGIN_ERROR_MESSAGES))
      } else if (err instanceof ApiError && err.code === 'VALIDATION_ERROR') {
        setErrors(err.fields)
      } else {
        setFormError(messageForError(err, ADMIN_LOGIN_ERROR_MESSAGES))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const locked = lockRemaining > 0

  return (
    <div className={styles.page}>
      <form className={styles.form} onSubmit={handleSubmit} data-testid="login-form" noValidate>
        <h1 className={styles.title}>관리자 로그인</h1>

        {sessionExpired ? (
          <ErrorNotice
            message="로그인이 만료되었어요. 다시 로그인해주세요."
            data-testid="login-session-expired"
          />
        ) : null}

        {formError ? (
          <ErrorNotice message={locked ? lockedMessage(lockRemaining) : formError} data-testid="login-error" />
        ) : null}

        <FormField label="매장 식별자" error={errors.storeId} data-testid="login-store-field">
          {(p) => (
            <input
              {...p}
              type="text"
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              className={styles.input}
              data-testid="login-store-input"
            />
          )}
        </FormField>
        <FormField label="사용자명" error={errors.username} data-testid="login-username-field">
          {(p) => (
            <input
              {...p}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={styles.input}
              data-testid="login-username-input"
            />
          )}
        </FormField>
        <FormField label="비밀번호" error={errors.password} data-testid="login-password-field">
          {(p) => (
            <input
              {...p}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
              data-testid="login-password-input"
            />
          )}
        </FormField>

        <Button
          type="submit"
          variant="primary"
          loading={submitting}
          disabled={locked}
          data-testid="login-submit-button"
        >
          {locked ? `${lockRemaining}초 후 가능` : '로그인'}
        </Button>
      </form>
    </div>
  )
}
