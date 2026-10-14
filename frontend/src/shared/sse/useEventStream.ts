import { useEffect, useRef, useState } from 'react'
import { useApiClient } from '../api/client'
import type { ServerEvent } from '../api/types'

export type StreamStatus = 'connecting' | 'open' | 'reconnecting'

const BACKOFF_STEPS_MS = [1000, 2000, 4000, 8000]
const MAX_BACKOFF_MS = 10_000

/** 재연결 대기 시간: 1s, 2s, 4s, 8s, 이후 10s */
export function computeBackoff(attempt: number): number {
  return BACKOFF_STEPS_MS[attempt] ?? MAX_BACKOFF_MS
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) return resolve()
    const timer = setTimeout(done, ms)
    function done() {
      clearTimeout(timer)
      signal.removeEventListener('abort', done)
      resolve()
    }
    signal.addEventListener('abort', done)
  })
}

export interface UseEventStreamOptions {
  enabled: boolean
  onEvent: (event: ServerEvent) => void
  /** 연결이 끊겼다가 다시 열렸을 때 (놓친 변경분을 위해 재조회) */
  onReconnected: () => void
}

/**
 * 관리자 실시간 이벤트 스트림.
 * ApiClient.streamAdminEvents를 연결하고, 끊기면 백오프로 재연결한다.
 */
export function useEventStream({ enabled, onEvent, onReconnected }: UseEventStreamOptions): { status: StreamStatus } {
  const client = useApiClient()
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const onEventRef = useRef(onEvent)
  const onReconnectedRef = useRef(onReconnected)

  useEffect(() => {
    onEventRef.current = onEvent
    onReconnectedRef.current = onReconnected
  })

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    const { signal } = controller
    let attempt = 0
    let dropped = false
    setStatus('connecting')

    void (async () => {
      while (!signal.aborted) {
        try {
          await client.streamAdminEvents({
            signal,
            onOpen: () => {
              if (signal.aborted) return
              attempt = 0
              setStatus('open')
              if (dropped) {
                dropped = false
                onReconnectedRef.current()
              }
            },
            onEvent: (e) => {
              if (!signal.aborted) onEventRef.current(e)
            },
          })
        } catch {
          // 오류도 끊김과 동일하게 재연결로 처리
        }
        if (signal.aborted) break
        dropped = true
        setStatus('reconnecting')
        await sleep(computeBackoff(attempt), signal)
        attempt += 1
      }
    })()

    return () => controller.abort()
  }, [enabled, client])

  return { status }
}
