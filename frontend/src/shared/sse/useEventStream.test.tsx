import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientContext } from '../api/client'
import type { ApiClient, EventStreamOptions } from '../api/client'
import type { ServerEvent } from '../api/types'
import { computeBackoff, useEventStream } from './useEventStream'

describe('computeBackoff', () => {
  it('1,2,4,8초 이후 10초로 고정', () => {
    expect([0, 1, 2, 3, 4, 5, 20].map(computeBackoff)).toEqual([1000, 2000, 4000, 8000, 10000, 10000, 10000])
  })
})

function makeClient(streams: Array<(o: EventStreamOptions) => Promise<void>>): ApiClient {
  let i = 0
  return {
    streamAdminEvents: (o: EventStreamOptions) => {
      const fn = streams[Math.min(i, streams.length - 1)]
      i += 1
      return fn(o)
    },
  } as unknown as ApiClient
}

function wrapperFor(client: ApiClient) {
  return ({ children }: { children: ReactNode }) => (
    <ApiClientContext.Provider value={client}>{children}</ApiClientContext.Provider>
  )
}

describe('useEventStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('연결되면 open 상태가 되고 이벤트를 전달한다', async () => {
    const event: ServerEvent = { type: 'order_created', tableId: 1, payload: {} }
    const client = makeClient([
      ({ onOpen, onEvent, signal }) =>
        new Promise<void>((resolve) => {
          onOpen()
          onEvent(event)
          signal.addEventListener('abort', () => resolve())
        }),
    ])
    const onEvent = vi.fn()
    const { result, unmount } = renderHook(
      () => useEventStream({ enabled: true, onEvent, onReconnected: vi.fn() }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.status).toBe('open')
    expect(onEvent).toHaveBeenCalledWith(event)
    unmount()
  })

  it('끊기면 reconnecting 상태가 되고 백오프 후 재연결하며 onReconnected를 호출한다', async () => {
    const onReconnected = vi.fn()
    const client = makeClient([
      // 1차: 열렸다가 즉시 종료(서버 끊김)
      async ({ onOpen }) => {
        onOpen()
      },
      // 2차: 열린 채 유지
      ({ onOpen, signal }) =>
        new Promise<void>((resolve) => {
          onOpen()
          signal.addEventListener('abort', () => resolve())
        }),
    ])
    const { result, unmount } = renderHook(
      () => useEventStream({ enabled: true, onEvent: vi.fn(), onReconnected }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.status).toBe('reconnecting')
    expect(onReconnected).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(result.current.status).toBe('open')
    expect(onReconnected).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('오류로 실패해도 재시도한다 (대기 시간 1초 -> 2초)', async () => {
    const calls: number[] = []
    const client = makeClient([
      async () => {
        calls.push(1)
        throw new Error('network')
      },
      async () => {
        calls.push(2)
        throw new Error('network')
      },
      ({ onOpen, signal }) =>
        new Promise<void>((resolve) => {
          calls.push(3)
          onOpen()
          signal.addEventListener('abort', () => resolve())
        }),
    ])
    const { result, unmount } = renderHook(
      () => useEventStream({ enabled: true, onEvent: vi.fn(), onReconnected: vi.fn() }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => {
      await Promise.resolve()
    })
    expect(calls).toEqual([1])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(calls).toEqual([1, 2])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1999)
    })
    expect(calls).toEqual([1, 2])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(calls).toEqual([1, 2, 3])
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.status).toBe('open')
    unmount()
  })

  it('enabled=false이면 연결하지 않는다', async () => {
    const streamAdminEvents = vi.fn()
    const client = { streamAdminEvents } as unknown as ApiClient
    renderHook(() => useEventStream({ enabled: false, onEvent: vi.fn(), onReconnected: vi.fn() }), {
      wrapper: wrapperFor(client),
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(streamAdminEvents).not.toHaveBeenCalled()
  })

  it('언마운트하면 스트림을 abort한다', async () => {
    let aborted = false
    const client = makeClient([
      ({ onOpen, signal }) =>
        new Promise<void>((resolve) => {
          onOpen()
          signal.addEventListener('abort', () => {
            aborted = true
            resolve()
          })
        }),
    ])
    const { unmount } = renderHook(
      () => useEventStream({ enabled: true, onEvent: vi.fn(), onReconnected: vi.fn() }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => {
      await Promise.resolve()
    })
    unmount()
    expect(aborted).toBe(true)
  })
})
