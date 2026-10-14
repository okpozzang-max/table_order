import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { useApiClient } from '../../shared/api/client'
import { configureAuthBridge, resetAuthBridge } from '../../shared/api/authBridge'
import { ApiError } from '../../shared/api/errors'
import { messageForError, TABLE_LOGIN_ERROR_MESSAGES } from '../../shared/utils/errorMessages'
import { Button } from '../../shared/ui'
import { Spinner } from '../../shared/ui'
import {
  clearTableCredentials,
  readTableCredentials,
  writeTableCredentials,
} from './storage'
import type { TableCredentials } from './storage'

export type TableAuthStatus = 'loading' | 'authenticated' | 'needs_setup' | 'error'

export interface TableAuthValue {
  status: TableAuthStatus
  tableNumber: number | null
  errorMessage?: string
  prefill?: { storeId: string; tableNumber: number }
  setup(storeId: string, tableNumber: number, password: string): Promise<void>
  retry(): void
  logout(): void
}

const TableAuthContext = createContext<TableAuthValue | null>(null)

const AUTO_RETRY_MS = 5000

export function TableAuthProvider({ children }: { children: ReactNode }) {
  const client = useApiClient()

  const [status, setStatus] = useState<TableAuthStatus>('loading')
  const [tableNumber, setTableNumber] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined)
  const [prefill, setPrefill] = useState<{ storeId: string; tableNumber: number } | undefined>(undefined)

  // 토큰은 메모리에만 보관한다.
  const tokenRef = useRef<string | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  /** 저장된 자격 증명으로 로그인한다. 결과 상태를 설정하고 성공 여부를 돌려준다. */
  const loginWithStored = useCallback(
    async (creds: TableCredentials): Promise<boolean> => {
      try {
        const res = await client.customerLogin({
          storeId: creds.storeId,
          tableNumber: creds.tableNumber,
          password: creds.password,
        })
        tokenRef.current = res.accessToken
        setTableNumber(res.tableNumber)
        setErrorMessage(undefined)
        setPrefill(undefined)
        setStatus('authenticated')
        return true
      } catch (err) {
        if (err instanceof ApiError && err.code === 'INVALID_CREDENTIALS') {
          tokenRef.current = null
          setErrorMessage(messageForError(err, TABLE_LOGIN_ERROR_MESSAGES))
          setPrefill({ storeId: creds.storeId, tableNumber: creds.tableNumber })
          setStatus('needs_setup')
          return false
        }
        // NETWORK_ERROR / INTERNAL_ERROR 등
        tokenRef.current = null
        setErrorMessage(messageForError(err, TABLE_LOGIN_ERROR_MESSAGES))
        setStatus('error')
        return false
      }
    },
    [client],
  )

  /** 앱 시작 / 수동 재시도 진입점. */
  const bootstrap = useCallback(async (): Promise<void> => {
    clearRetryTimer()
    const creds = readTableCredentials()
    if (!creds) {
      setStatus('needs_setup')
      setErrorMessage(undefined)
      setPrefill(undefined)
      return
    }
    setStatus('loading')
    await loginWithStored(creds)
  }, [clearRetryTimer, loginWithStored])

  // 마운트 시 1회 부트스트랩.
  useEffect(() => {
    void bootstrap()
    return clearRetryTimer
  }, [bootstrap, clearRetryTimer])

  // error 상태에서는 5초마다 자동 재시도한다.
  useEffect(() => {
    if (status !== 'error') {
      clearRetryTimer()
      return
    }
    retryTimerRef.current = setTimeout(() => {
      void bootstrap()
    }, AUTO_RETRY_MS)
    return clearRetryTimer
  }, [status, bootstrap, clearRetryTimer])

  // authBridge 등록: 토큰 공급 + UNAUTHORIZED 재로그인.
  useEffect(() => {
    const handleTableUnauthorized = async (): Promise<boolean> => {
      const creds = readTableCredentials()
      if (!creds) {
        tokenRef.current = null
        setStatus('needs_setup')
        return false
      }
      const ok = await loginWithStored(creds)
      return ok
    }
    configureAuthBridge({
      getTableToken: () => tokenRef.current,
      handleTableUnauthorized,
    })
    return () => {
      resetAuthBridge()
    }
  }, [loginWithStored])

  const setup = useCallback(
    async (storeId: string, tn: number, password: string): Promise<void> => {
      clearRetryTimer()
      setStatus('loading')
      try {
        const res = await client.customerLogin({ storeId, tableNumber: tn, password })
        tokenRef.current = res.accessToken
        writeTableCredentials({ storeId, tableNumber: tn, password })
        setTableNumber(res.tableNumber)
        setErrorMessage(undefined)
        setPrefill(undefined)
        setStatus('authenticated')
      } catch (err) {
        // 자격 증명을 저장하지 않는다. 설정 화면으로 돌아간다.
        tokenRef.current = null
        setStatus('needs_setup')
        throw err
      }
    },
    [client, clearRetryTimer],
  )

  const retry = useCallback(() => {
    void bootstrap()
  }, [bootstrap])

  const logout = useCallback(() => {
    clearRetryTimer()
    tokenRef.current = null
    clearTableCredentials()
    setTableNumber(null)
    setErrorMessage(undefined)
    setPrefill(undefined)
    setStatus('needs_setup')
  }, [clearRetryTimer])

  const value = useMemo<TableAuthValue>(
    () => ({ status, tableNumber, errorMessage, prefill, setup, retry, logout }),
    [status, tableNumber, errorMessage, prefill, setup, retry, logout],
  )

  return <TableAuthContext.Provider value={value}>{children}</TableAuthContext.Provider>
}

export function useTableAuth(): TableAuthValue {
  const ctx = useContext(TableAuthContext)
  if (!ctx) throw new Error('TableAuthProvider 안에서만 useTableAuth를 사용할 수 있어요.')
  return ctx
}

/** 셸 가드가 로딩 상태에서 렌더링하는 화면. */
export function TableAuthLoadingScreen() {
  return (
    <div
      style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}
      data-testid="table-auth-loading"
    >
      <Spinner label="테이블 정보를 확인하는 중..." />
    </div>
  )
}

/** 셸 가드가 error 상태에서 렌더링하는 화면. */
export function TableAuthErrorScreen() {
  const { errorMessage, retry } = useTableAuth()
  return (
    <div
      style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 'var(--space-5)' }}
      data-testid="table-auth-error"
    >
      <div style={{ textAlign: 'center', maxWidth: 420 }}>
        <p role="alert" data-testid="table-auth-error-message">
          {errorMessage ?? '서버에 연결할 수 없어요. 잠시 후 다시 시도해주세요.'}
        </p>
        <p style={{ color: 'var(--color-text-muted)' }}>잠시 후 자동으로 다시 시도해요.</p>
        <Button variant="primary" onClick={retry} data-testid="table-auth-retry-button">
          다시 시도
        </Button>
      </div>
    </div>
  )
}
