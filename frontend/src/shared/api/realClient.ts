import { callWithAuth, authBridge } from './authBridge'
import type { AuthKind } from './authBridge'
import type { ApiClient, EventStreamOptions } from './client'
import { ApiError, networkError, parseErrorResponse } from './errors'
import type { ServerEvent } from './types'
import { SseParser } from '../sse/sseParser'

const REQUEST_TIMEOUT_MS = 15_000

interface RequestOptions {
  auth: AuthKind
  query?: Record<string, string | number | null | undefined>
  body?: unknown
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

async function request<T>(method: string, path: string, opts: RequestOptions): Promise<T> {
  return callWithAuth(opts.auth, async (token) => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    if (token) headers.Authorization = `Bearer ${token}`

    let res: Response
    try {
      res = await fetch(buildUrl(path, opts.query), {
        method,
        headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
        signal: controller.signal,
      })
    } catch {
      throw networkError()
    } finally {
      clearTimeout(timer)
    }

    if (!res.ok) throw await parseErrorResponse(res)
    if (res.status === 204) return undefined as T
    try {
      return (await res.json()) as T
    } catch {
      throw new ApiError(res.status, 'INTERNAL_ERROR')
    }
  })
}

async function streamEvents(opts: EventStreamOptions): Promise<void> {
  const token = authBridge.getAdminToken()
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (token) headers.Authorization = `Bearer ${token}`

  let res: Response
  try {
    res = await fetch('/api/admin/events', { headers, signal: opts.signal })
  } catch {
    if (opts.signal.aborted) return
    throw networkError()
  }
  if (!res.ok || !res.body) {
    const err = await parseErrorResponse(res)
    if (err.code === 'UNAUTHORIZED') authBridge.handleAdminUnauthorized()
    throw err
  }

  opts.onOpen()
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  const parser = new SseParser()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) return
      for (const ev of parser.push(decoder.decode(value, { stream: true }))) {
        try {
          opts.onEvent(JSON.parse(ev.data) as ServerEvent)
        } catch {
          // 형식이 잘못된 이벤트는 무시
        }
      }
    }
  } catch {
    if (opts.signal.aborted) return
    throw networkError()
  } finally {
    reader.releaseLock()
  }
}

export function createRealClient(): ApiClient {
  return {
    customerLogin: (req) => request('POST', '/api/customer/auth/login', { auth: 'none', body: req }),
    getCustomerMenus: () => request('GET', '/api/customer/menus', { auth: 'table' }),
    createOrder: (req) => request('POST', '/api/customer/orders', { auth: 'table', body: req }),
    listSessionOrders: (page, size) =>
      request('GET', '/api/customer/orders', { auth: 'table', query: { page, size } }),

    adminLogin: (req) => request('POST', '/api/admin/auth/login', { auth: 'none', body: req }),

    getDashboard: (table) =>
      request('GET', '/api/admin/dashboard', { auth: 'admin', query: { table: table ?? undefined } }),
    getOrder: (id) => request('GET', `/api/admin/orders/${id}`, { auth: 'admin' }),
    changeOrderStatus: (id, status) =>
      request('PATCH', `/api/admin/orders/${id}/status`, { auth: 'admin', body: { status } }),
    deleteOrder: (id) => request('DELETE', `/api/admin/orders/${id}`, { auth: 'admin' }),
    streamAdminEvents: streamEvents,

    listTables: () => request('GET', '/api/admin/tables', { auth: 'admin' }),
    registerTable: (req) => request('POST', '/api/admin/tables', { auth: 'admin', body: req }),
    endSession: (tableId) => request('POST', `/api/admin/tables/${tableId}/end-session`, { auth: 'admin' }),
    getTableHistory: (tableId, range) =>
      request('GET', `/api/admin/tables/${tableId}/history`, {
        auth: 'admin',
        query: { from: range?.from, to: range?.to },
      }),

    listAdminMenus: () => request('GET', '/api/admin/menus', { auth: 'admin' }),
    createMenu: (input) => request('POST', '/api/admin/menus', { auth: 'admin', body: input }),
    updateMenu: (id, input) => request('PUT', `/api/admin/menus/${id}`, { auth: 'admin', body: input }),
    deleteMenu: (id) => request('DELETE', `/api/admin/menus/${id}`, { auth: 'admin' }),
    reorderMenus: (category, orderedIds) =>
      request('PUT', '/api/admin/menus/reorder', { auth: 'admin', body: { category, orderedIds } }),
  }
}
