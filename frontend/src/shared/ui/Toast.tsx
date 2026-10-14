import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import styles from './Toast.module.css'

export type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  type: ToastType
  message: string
}

interface ToastApi {
  show(type: ToastType, message: string): void
  success(message: string): void
  error(message: string): void
}

const ToastContext = createContext<ToastApi | null>(null)

const DURATION_MS: Record<ToastType, number> = { success: 3000, info: 3000, error: 5000 }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) clearTimeout(timer)
    timers.current.delete(id)
  }, [])

  const show = useCallback(
    (type: ToastType, message: string) => {
      const id = nextId.current++
      setItems((prev) => [...prev, { id, type, message }])
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), DURATION_MS[type]),
      )
    },
    [dismiss],
  )

  useEffect(() => {
    const map = timers.current
    return () => {
      map.forEach((t) => clearTimeout(t))
      map.clear()
    }
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      show,
      success: (m) => show('success', m),
      error: (m) => show('error', m),
    }),
    [show],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.container} data-testid="toast-container">
        {items.map((t) => (
          <div
            key={t.id}
            className={`${styles.toast} ${styles[t.type]}`}
            role={t.type === 'error' ? 'alert' : 'status'}
            data-testid={`toast-${t.type}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('ToastProvider 안에서만 useToast를 사용할 수 있어요.')
  return ctx
}
