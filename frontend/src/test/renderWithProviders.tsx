import { render } from '@testing-library/react'
import type { RenderResult } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import { ApiClientContext } from '../shared/api/client'
import type { ApiClient } from '../shared/api/client'
import { resetAuthBridge } from '../shared/api/authBridge'
import { ToastProvider } from '../shared/ui/Toast'
import { MockBackend } from '../mocks/mockBackend'
import { createMockClient } from '../mocks/mockClient'

export interface TestHarness {
  backend: MockBackend
  client: ApiClient
  queryClient: QueryClient
}

export function createTestHarness(opts: { now?: () => number } = {}): TestHarness {
  const backend = new MockBackend({ now: opts.now })
  const client = createMockClient(backend, { delay: () => 0, forcedError: () => null })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return { backend, client, queryClient }
}

export interface RenderOptions {
  /** 초기 경로 (MemoryRouter) */
  route?: string
  harness?: TestHarness
  /** 추가 Provider로 감싸기 (예: TableAuthProvider, CartProvider) */
  wrapper?: (children: ReactElement) => ReactElement
}

/**
 * ApiClient(가짜 백엔드, 지연 0), QueryClient(재시도 없음), Toast, Router를 갖춘 환경에서 렌더링한다.
 * 테스트마다 새 MockBackend를 사용하므로 서로 영향을 주지 않는다.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions = {},
): RenderResult & TestHarness {
  resetAuthBridge()
  const harness = options.harness ?? createTestHarness()
  const inner = options.wrapper ? options.wrapper(ui) : ui
  const result = render(
    <ApiClientContext.Provider value={harness.client}>
      <QueryClientProvider client={harness.queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[options.route ?? '/']}>{inner}</MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ApiClientContext.Provider>,
  )
  return { ...result, ...harness }
}
