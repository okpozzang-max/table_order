import { callWithAuth, authBridge } from '../shared/api/authBridge'
import type { AuthKind } from '../shared/api/authBridge'
import type { ApiClient } from '../shared/api/client'
import { ApiError, networkError } from '../shared/api/errors'
import { MockBackend } from './mockBackend'

export interface MockClientOptions {
  /** 요청 지연(ms). 기본 150~400ms 무작위. 테스트에서는 0 */
  delay?: () => number
  /** 강제 오류 모드를 읽는 함수. 기본은 URL의 ?mockError=network|server */
  forcedError?: () => 'network' | 'server' | null
}

function defaultDelay(): number {
  return 150 + Math.random() * 250
}

function defaultForcedError(): 'network' | 'server' | null {
  if (typeof window === 'undefined') return null
  const v = new URLSearchParams(window.location.search).get('mockError')
  return v === 'network' || v === 'server' ? v : null
}

const wait = (ms: number) => (ms > 0 ? new Promise<void>((r) => setTimeout(r, ms)) : Promise.resolve())

/** MockBackend를 ApiClient 인터페이스로 감싼다. 실제 클라이언트와 같은 인증 처리(callWithAuth)를 사용한다. */
export function createMockClient(backend: MockBackend, options: MockClientOptions = {}): ApiClient {
  const delay = options.delay ?? defaultDelay
  const forced = options.forcedError ?? defaultForcedError

  async function call<T>(kind: AuthKind, op: (token: string | null) => T): Promise<T> {
    return callWithAuth(kind, async (token) => {
      await wait(delay())
      const f = forced()
      if (f === 'network') throw networkError()
      if (f === 'server') throw new ApiError(500, 'INTERNAL_ERROR', { code: 'INTERNAL_ERROR' })
      return op(token)
    })
  }

  return {
    customerLogin: (req) => call('none', () => backend.customerLogin(req)),
    getCustomerMenus: () => call('table', (t) => backend.getCustomerMenus(t)),
    createOrder: (req) => call('table', (t) => backend.createOrder(t, req)),
    listSessionOrders: (page, size) => call('table', (t) => backend.listSessionOrders(t, page, size)),

    adminLogin: (req) => call('none', () => backend.adminLogin(req)),

    getDashboard: (table) => call('admin', (t) => backend.getDashboard(t, table)),
    getOrder: (id) => call('admin', (t) => backend.getOrder(t, id)),
    changeOrderStatus: (id, status) => call('admin', (t) => backend.changeOrderStatus(t, id, status)),
    deleteOrder: (id) => call('admin', (t) => backend.deleteOrder(t, id)),
    streamAdminEvents: async ({ signal, onOpen, onEvent }) => {
      const token = authBridge.getAdminToken()
      try {
        const stream = backend.streamAdminEvents(token, onEvent, signal)
        onOpen()
        await stream
      } catch (e) {
        if (e instanceof ApiError && e.code === 'UNAUTHORIZED') authBridge.handleAdminUnauthorized()
        throw e
      }
    },

    listTables: () => call('admin', (t) => backend.listTables(t)),
    registerTable: (req) => call('admin', (t) => backend.registerTable(t, req)),
    endSession: (id) => call('admin', (t) => backend.endSession(t, id)),
    getTableHistory: (id, range) => call('admin', (t) => backend.getTableHistory(t, id, range)),

    listAdminMenus: () => call('admin', (t) => backend.listAdminMenus(t)),
    createMenu: (input) => call('admin', (t) => backend.createMenu(t, input)),
    updateMenu: (id, input) => call('admin', (t) => backend.updateMenu(t, id, input)),
    deleteMenu: (id) => call('admin', (t) => backend.deleteMenu(t, id)),
    reorderMenus: (category, ids) => call('admin', (t) => backend.reorderMenus(t, category, ids)),
  }
}

export const MOCK_STORAGE_KEY = 'tableorder.mock.store.v1'
export const MOCK_CHANNEL_NAME = 'tableorder.mock.events'

/** 개발용 공유 인스턴스: localStorage + BroadcastChannel로 탭 간 공유 */
export function createSharedMockClient(): ApiClient {
  const backend = new MockBackend({ storageKey: MOCK_STORAGE_KEY, channelName: MOCK_CHANNEL_NAME })
  return createMockClient(backend)
}
