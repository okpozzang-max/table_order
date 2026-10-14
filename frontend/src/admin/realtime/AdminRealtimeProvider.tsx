import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useEventStream } from '../../shared/sse/useEventStream'
import type { StreamStatus } from '../../shared/sse/useEventStream'
import type { ServerEvent } from '../../shared/api/types'

export interface AdminRealtime {
  status: StreamStatus
  /** 테이블별 아직 확인하지 않은 주문 ID 목록 (메모리 전용) */
  unseen: Record<number, number[]>
  markSeen(tableId: number): void
  refreshNow(): void
}

const AdminRealtimeContext = createContext<AdminRealtime | null>(null)

export function AdminRealtimeProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [unseen, setUnseen] = useState<Record<number, number[]>>({})
  // orderId가 없는 order_created를 위한 음수 카운터
  const fallbackId = useRef(-1)

  const invalidateAdmin = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['admin'] })
  }, [queryClient])

  const onEvent = useCallback(
    (event: ServerEvent) => {
      invalidateAdmin()
      if (event.type === 'order_created' && event.tableId != null) {
        const tableId = event.tableId
        const rawId = (event.payload as { orderId?: unknown }).orderId
        const orderId = typeof rawId === 'number' ? rawId : fallbackId.current--
        setUnseen((prev) => {
          const existing = prev[tableId] ?? []
          if (existing.includes(orderId)) return prev
          return { ...prev, [tableId]: [...existing, orderId] }
        })
      }
    },
    [invalidateAdmin],
  )

  const onReconnected = useCallback(() => {
    invalidateAdmin()
  }, [invalidateAdmin])

  const { status } = useEventStream({ enabled: true, onEvent, onReconnected })

  const markSeen = useCallback((tableId: number) => {
    setUnseen((prev) => {
      if (!prev[tableId] || prev[tableId].length === 0) return prev
      const next = { ...prev }
      delete next[tableId]
      return next
    })
  }, [])

  const refreshNow = useCallback(() => {
    invalidateAdmin()
  }, [invalidateAdmin])

  const value = useMemo<AdminRealtime>(
    () => ({ status, unseen, markSeen, refreshNow }),
    [markSeen, refreshNow, status, unseen],
  )

  return <AdminRealtimeContext.Provider value={value}>{children}</AdminRealtimeContext.Provider>
}

export function useAdminRealtime(): AdminRealtime {
  const ctx = useContext(AdminRealtimeContext)
  if (!ctx) throw new Error('AdminRealtimeProvider 안에서만 useAdminRealtime을 사용할 수 있어요.')
  return ctx
}
