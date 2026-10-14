import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiClientContext } from '../../shared/api/client'
import type { ApiClient } from '../../shared/api/client'
import { resetAuthBridge } from '../../shared/api/authBridge'
import { ApiError } from '../../shared/api/errors'
import { ToastProvider } from '../../shared/ui/Toast'
import { MockBackend } from '../../mocks/mockBackend'
import { createMockClient } from '../../mocks/mockClient'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID } from '../../mocks/seed'
import { writeAdminAuth } from '../auth/storage'
import { AdminAuthProvider } from '../auth/AdminAuthProvider'
import { AdminLayout } from './AdminLayout'

/** streamAdminEvents가 즉시 reject하는 클라이언트 (재연결 상태 모사) */
function makeFailingStreamClient(backend: MockBackend): ApiClient {
  const base = createMockClient(backend, { delay: () => 0, forcedError: () => null })
  return {
    ...base,
    streamAdminEvents: async () => {
      throw new ApiError(0, 'NETWORK_ERROR')
    },
  }
}

function renderLayout(client: ApiClient, backend: MockBackend) {
  resetAuthBridge()
  const res = backend.adminLogin({
    storeId: MOCK_STORE_ID,
    username: MOCK_ADMIN_USERNAME,
    password: MOCK_ADMIN_PASSWORD,
  })
  writeAdminAuth({ accessToken: res.accessToken, expiresAt: res.expiresAt })

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return render(
    <ApiClientContext.Provider value={client}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/admin/dashboard']}>
            <AdminAuthProvider>
              <Routes>
                <Route path="/admin" element={<AdminLayout />}>
                  <Route path="dashboard" element={<div data-testid="page">PAGE</div>} />
                </Route>
              </Routes>
            </AdminAuthProvider>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ApiClientContext.Provider>,
  )
}

describe('AdminLayout + ConnectionIndicator', () => {
  it('renders the nav links and the routed outlet', async () => {
    const backend = new MockBackend({ now: () => Date.now() })
    const client = createMockClient(backend, { delay: () => 0, forcedError: () => null })
    renderLayout(client, backend)
    expect(screen.getByTestId('admin-nav-dashboard')).toBeTruthy()
    expect(screen.getByTestId('admin-nav-tables')).toBeTruthy()
    expect(screen.getByTestId('admin-nav-menus')).toBeTruthy()
    expect(screen.getByTestId('page')).toBeTruthy()
  })

  it('shows the reconnecting state when the stream keeps failing', async () => {
    const backend = new MockBackend({ now: () => Date.now() })
    const client = makeFailingStreamClient(backend)
    renderLayout(client, backend)

    await waitFor(() => {
      expect(screen.getByTestId('connection-indicator').getAttribute('data-status')).toBe('reconnecting')
    })
  })
})
