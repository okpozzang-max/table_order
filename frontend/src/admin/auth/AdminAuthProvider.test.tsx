import { describe, expect, it } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import { createTestHarness } from '../../test/renderWithProviders'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID } from '../../mocks/seed'
import { authBridge } from '../../shared/api/authBridge'
import { ADMIN_AUTH_STORAGE_KEY, readAdminAuth, writeAdminAuth } from '../auth/storage'
import { AdminAuthProvider, useAdminAuth } from '../auth/AdminAuthProvider'

function AuthProbe() {
  const auth = useAdminAuth()
  return (
    <div>
      <span data-testid="is-auth">{String(auth.isAuthenticated)}</span>
      <span data-testid="expired">{String(auth.sessionExpired)}</span>
      <span data-testid="expires">{auth.expiresAt ?? 'null'}</span>
      <button
        type="button"
        data-testid="do-login"
        onClick={() => {
          void auth.login(MOCK_STORE_ID, MOCK_ADMIN_USERNAME, MOCK_ADMIN_PASSWORD)
        }}
      >
        login
      </button>
      <button type="button" data-testid="do-logout" onClick={() => auth.logout()}>
        logout
      </button>
    </div>
  )
}

const wrap = (ui: React.ReactElement) => <AdminAuthProvider>{ui}</AdminAuthProvider>

describe('AdminAuthProvider', () => {
  it('login success stores token and authenticates', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AuthProbe />, { wrapper: wrap })

    expect(screen.getByTestId('is-auth').textContent).toBe('false')
    await user.click(screen.getByTestId('do-login'))

    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('true'))
    expect(readAdminAuth()).not.toBeNull()
    expect(readAdminAuth()?.accessToken).toMatch(/^mock-admin\./)
  })

  it('restores a valid token from storage on mount', async () => {
    const harness = createTestHarness()
    const res = harness.backend.adminLogin({
      storeId: MOCK_STORE_ID,
      username: MOCK_ADMIN_USERNAME,
      password: MOCK_ADMIN_PASSWORD,
    })
    writeAdminAuth({ accessToken: res.accessToken, expiresAt: res.expiresAt })

    renderWithProviders(<AuthProbe />, { harness, wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('true'))
    expect(authBridge.getAdminToken()).toBe(res.accessToken)
  })

  it('drops an expired token on mount', async () => {
    writeAdminAuth({
      accessToken: 'mock-admin.1',
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    })
    renderWithProviders(<AuthProbe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('false'))
    expect(localStorage.getItem(ADMIN_AUTH_STORAGE_KEY)).toBeNull()
  })

  it('handleAdminUnauthorized sets sessionExpired and clears token', async () => {
    const harness = createTestHarness()
    const res = harness.backend.adminLogin({
      storeId: MOCK_STORE_ID,
      username: MOCK_ADMIN_USERNAME,
      password: MOCK_ADMIN_PASSWORD,
    })
    writeAdminAuth({ accessToken: res.accessToken, expiresAt: res.expiresAt })

    renderWithProviders(<AuthProbe />, { harness, wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('true'))

    act(() => {
      authBridge.handleAdminUnauthorized()
    })

    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('false'))
    expect(screen.getByTestId('expired').textContent).toBe('true')
    expect(localStorage.getItem(ADMIN_AUTH_STORAGE_KEY)).toBeNull()
  })

  it('logout clears token and resets sessionExpired', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AuthProbe />, { wrapper: wrap })
    await user.click(screen.getByTestId('do-login'))
    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('true'))

    await user.click(screen.getByTestId('do-logout'))
    await waitFor(() => expect(screen.getByTestId('is-auth').textContent).toBe('false'))
    expect(screen.getByTestId('expired').textContent).toBe('false')
    expect(localStorage.getItem(ADMIN_AUTH_STORAGE_KEY)).toBeNull()
  })
})
