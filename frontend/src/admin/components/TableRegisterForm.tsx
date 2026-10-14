import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button, FormField, useToast } from '../../shared/ui'
import { validateTableRegister } from '../../shared/utils/validators'
import type { FieldErrors } from '../../shared/utils/validators'
import { messageForError } from '../../shared/utils/errorMessages'
import { ApiError } from '../../shared/api/errors'
import { useRegisterTable } from '../hooks/useAdminQueries'
import styles from './TableRegisterForm.module.css'

export function TableRegisterForm() {
  const toast = useToast()
  const register = useRegisterTable()
  const [tableNumber, setTableNumber] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const result = validateTableRegister({ tableNumber, password })
    if (!result.value) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    register.mutate(result.value, {
      onSuccess: (table) => {
        toast.success(`테이블 ${table.tableNumber}을(를) 등록했어요.`)
        setTableNumber('')
        setPassword('')
      },
      onError: (err) => {
        if (err instanceof ApiError && err.code === 'DUPLICATE_TABLE') {
          setErrors({ tableNumber: '이미 등록된 테이블 번호예요.' })
          toast.error('이미 등록된 테이블 번호예요.')
        } else if (err instanceof ApiError && err.code === 'VALIDATION_ERROR') {
          setErrors(err.fields)
        } else {
          toast.error(messageForError(err))
        }
      },
    })
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} data-testid="table-register-form" noValidate>
      <h3 className={styles.title}>테이블 등록</h3>
      <FormField label="테이블 번호" error={errors.tableNumber} data-testid="table-register-number-field">
        {(p) => (
          <input
            {...p}
            type="text"
            inputMode="numeric"
            value={tableNumber}
            onChange={(e) => setTableNumber(e.target.value)}
            className={styles.input}
            data-testid="table-register-number-input"
          />
        )}
      </FormField>
      <FormField label="비밀번호 (숫자 4자리)" error={errors.password} data-testid="table-register-password-field">
        {(p) => (
          <input
            {...p}
            type="password"
            inputMode="numeric"
            maxLength={4}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={styles.input}
            data-testid="table-register-password-input"
          />
        )}
      </FormField>
      <p className={styles.guide} data-testid="table-register-guide">
        등록 후 태블릿에서 <code>/customer/setup</code> 화면에 접속해 같은 매장 식별자, 테이블 번호,
        비밀번호로 초기 설정을 완료해주세요.
      </p>
      <Button
        type="submit"
        variant="primary"
        loading={register.isPending}
        data-testid="table-register-submit-button"
      >
        등록
      </Button>
    </form>
  )
}
