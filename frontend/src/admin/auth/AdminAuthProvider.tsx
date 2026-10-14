import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { configureAuthBridge } from '../../shared/api/authBridge'
import { useApiClient } from '../../shared/api/client'
import {
  ADMIN_AUTH_STORAGE_KEY,
  clearAdminAuth,
  isFuture,
  readAdminAuth,
  writeAdminAuth,
} from './storage'

export interface AdminAuth {
  isAuthenticated: boolean
  expiresAt: string | null
  sessionExpired: boolean
  login(storeId: string, username: string, password: string): Promise<void>
  logout(): void
}

const AdminAuthContext = createContext<AdminAuth | null>(null)

/** setTimeout의 큰 지연을 안전하게 처리하기 위한 최대 간격 (24시간) */
const MAX_TIMEOUT_MS = 24 * 60 * 60 * 1000

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const client = useApiClient()
  const queryClient = useQueryClient()

  // 마운트 시점의 저장 토큰을 동기적으로 읽어 초기 상태를 만든다.
  // (자식 쿼리의 effect가 Provider의 effect보다 먼저 실행되므로, 토큰은 첫 렌더부터 유효해야 한다)
  const initial = useRef<{ token: string | null; expiresAt: string | null } | undefined>(undefined)
  if (!initial.current) {
    const stored = readAdminAuth()
    if (stored && isFuture(stored.expiresAt, Date.now())) {
      initial.current = { token: stored.accessToken, expiresAt: stored.expiresAt }
    } else {
      if (stored) clearAdminAuth()
      initial.current = { token: null, expiresAt: null }
    }
  }

  const tokenRef = useRef<string | null>(initial.current.token)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bridgeConfigured = useRef(false)

  const [expiresAt, setExpiresAt] = useState<string | null>(initial.current.expiresAt)
  const [isAuthenticated, setIsAuthenticated] = useState(initial.current.token !== null)
  const [sessionExpired, setSessionExpired] = useState(false)

  // 자식 effect보다 먼저(렌더 중) 브리지를 등록해, 첫 쿼리가 토큰을 읽을 수 있게 한다.
  if (!bridgeConfigured.current) {
    bridgeConfigured.current = true
    configureAuthBridge({
      getAdminToken: () => tokenRef.current,
      handleAdminUnauthorized: () => {
        tokenRef.current = null
        clearAdminAuth()
        if (timerRef.current) {
          clearTimeout(timerRef.current)
          timerRef.current = null
        }
        setIsAuthenticated(false)
        setExpiresAt(null)
        queryClient.clear()
        setSessionExpired(true)
      },
    })
  }

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  /** 만료 시각에 자동 로그아웃. 큰 지연은 24시간 조각으로 나눠 재설정한다. */
  const scheduleExpiry = useCallback(
    (expiry: string, onExpire: () => void) => {
      clearTimer()
      const arm = () => {
        const remaining = new Date(expiry).getTime() - Date.now()
        if (remaining <= 0) {
          onExpire()
          return
        }
        const step = Math.min(remaining, MAX_TIMEOUT_MS)
        timerRef.current = setTimeout(arm, step)
      }
      arm()
    },
    [clearTimer],
  )

  const applyLoggedOut = useCallback(() => {
    tokenRef.current = null
    clearAdminAuth()
    clearTimer()
    setIsAuthenticated(false)
    setExpiresAt(null)
  }, [clearTimer])

  // 토큰 만료 자동 로그아웃
  const expireNow = useCallback(() => {
    applyLoggedOut()
    queryClient.clear()
    setSessionExpired(true)
  }, [applyLoggedOut, queryClient])

  const applyAuthenticated = useCallback(
    (accessToken: string, expiry: string) => {
      tokenRef.current = accessToken
      setExpiresAt(expiry)
      setIsAuthenticated(true)
      scheduleExpiry(expiry, expireNow)
    },
    [expireNow, scheduleExpiry],
  )

  const login = useCallback(
    async (storeId: string, username: string, password: string) => {
      const res = await client.adminLogin({ storeId, username, password })
      writeAdminAuth({ accessToken: res.accessToken, expiresAt: res.expiresAt })
      applyAuthenticated(res.accessToken, res.expiresAt)
      setSessionExpired(false)
    },
    [applyAuthenticated, client],
  )

  const logout = useCallback(() => {
    applyLoggedOut()
    queryClient.clear()
    setSessionExpired(false)
  }, [applyLoggedOut, queryClient])

  // 마운트: 복원된 토큰이 있으면 만료 타이머만 건다. (브리지는 렌더 중에 이미 등록됨)
  useEffect(() => {
    if (initial.current && initial.current.expiresAt) {
      scheduleExpiry(initial.current.expiresAt, expireNow)
    }
    return () => {
      clearTimer()
    }
    // 마운트 1회만 실행 (의도적)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 다른 탭에서 토큰이 삭제되면 동기화 (선택적 안전장치)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === ADMIN_AUTH_STORAGE_KEY && e.newValue === null) {
        applyLoggedOut()
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [applyLoggedOut])

  const value = useMemo<AdminAuth>(
    () => ({ isAuthenticated, expiresAt, sessionExpired, login, logout }),
    [expiresAt, isAuthenticated, login, logout, sessionExpired],
  )

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}

export function useAdminAuth(): AdminAuth {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('AdminAuthProvider 안에서만 useAdminAuth를 사용할 수 있어요.')
  return ctx
}
