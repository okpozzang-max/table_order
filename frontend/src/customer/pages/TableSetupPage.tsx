import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { messageForError, TABLE_LOGIN_ERROR_MESSAGES } from '../../shared/utils/errorMessages'
import { validateTableSetup } from '../../shared/utils/validators'
import type { FieldErrors } from '../../shared/utils/validators'
import { Button, FormField } from '../../shared/ui'
import { useTableAuth } from '../auth/TableAuthProvider'
import styles from './TableSetupPage.module.css'

export function TableSetupPage() {
  const { setup, prefill, errorMessage } = useTableAuth()
  const navigate = useNavigate()

  const [storeId, setStoreId] = useState('')
  const [tableNumber, setTableNumber] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [serverError, setServerError] = useState<string | undefined>(errorMessage)
  const [submitting, setSubmitting] = useState(false)

  // 자격 증명 오류로 돌아온 경우 매장/테이블 번호를 미리 채운다 (비밀번호는 비움).
  useEffect(() => {
    if (prefill) {
      setStoreId(prefill.storeId)
      setTableNumber(String(prefill.tableNumber))
    }
  }, [prefill])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setServerError(undefined)
    const result = validateTableSetup({ storeId, tableNumber, password })
    setFieldErrors(result.errors)
    if (!result.value) return
    setSubmitting(true)
    try {
      await setup(result.value.storeId, result.value.tableNumber, result.value.password)
      navigate('/customer/menu')
    } catch (err) {
      setServerError(messageForError(err, TABLE_LOGIN_ERROR_MESSAGES))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.wrap} data-testid="table-setup-page">
      <form className={styles.card} onSubmit={onSubmit} noValidate>
        <h1 className={styles.title}>테이블 설정</h1>
        <p className={styles.subtitle}>매장에서 안내받은 정보를 입력해주세요.</p>

        {serverError ? (
          <div role="alert" className={styles.serverError} data-testid="table-setup-server-error">
            {serverError}
          </div>
        ) : null}

        <FormField label="매장 식별자" error={fieldErrors.storeId} data-testid="table-setup-field-storeId">
          {(props) => (
            <input
              {...props}
              className={styles.input}
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              autoComplete="off"
              data-testid="table-setup-input-storeId"
            />
          )}
        </FormField>

        <FormField label="테이블 번호" error={fieldErrors.tableNumber} data-testid="table-setup-field-tableNumber">
          {(props) => (
            <input
              {...props}
              className={styles.input}
              value={tableNumber}
              onChange={(e) => setTableNumber(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
              data-testid="table-setup-input-tableNumber"
            />
          )}
        </FormField>

        <FormField label="비밀번호 (숫자 4자리)" error={fieldErrors.password} data-testid="table-setup-field-password">
          {(props) => (
            <input
              {...props}
              className={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              inputMode="numeric"
              maxLength={4}
              autoComplete="off"
              data-testid="table-setup-input-password"
            />
          )}
        </FormField>

        <Button
          type="submit"
          variant="primary"
          loading={submitting}
          className={styles.submit}
          data-testid="table-setup-submit-button"
        >
          시작하기
        </Button>
      </form>
    </div>
  )
}
