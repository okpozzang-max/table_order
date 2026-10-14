import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID } from '../../mocks/seed'
import { AdminAuthProvider } from '../auth/AdminAuthProvider'
import { LoginPage } from './LoginPage'

const wrap = (ui: React.ReactElement) => <AdminAuthProvider>{ui}</AdminAuthProvider>

function LoginRoutes() {
  return (
    <Routes>
      <Route path="/admin/login" element={<LoginPage />} />
      <Route path="/admin/dashboard" element={<div data-testid="dashboard-page">DASH</div>} />
      <Route path="/admin/menus" element={<div data-testid="menus-page">MENUS</div>} />
    </Routes>
  )
}

describe('LoginPage', () => {
  it('shows validation errors on empty submit', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginRoutes />, { wrapper: wrap, route: '/admin/login' })
    await user.click(screen.getByTestId('login-submit-button'))
    expect(screen.getByTestId('login-store-field-error')).toBeTruthy()
    expect(screen.getByTestId('login-username-field-error')).toBeTruthy()
    expect(screen.getByTestId('login-password-field-error')).toBeTruthy()
  })

  it('shows an error message for wrong credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginRoutes />, { wrapper: wrap, route: '/admin/login' })
    await user.type(screen.getByTestId('login-store-input'), MOCK_STORE_ID)
    await user.type(screen.getByTestId('login-username-input'), MOCK_ADMIN_USERNAME)
    await user.type(screen.getByTestId('login-password-input'), 'wrongpass')
    await user.click(screen.getByTestId('login-submit-button'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error').textContent).toContain('맞지 않아요')
    })
  })

  it('locks the submit button and counts down after reaching the failure limit', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginRoutes />, { wrapper: wrap, route: '/admin/login' })

    await user.type(screen.getByTestId('login-store-input'), MOCK_STORE_ID)
    await user.type(screen.getByTestId('login-username-input'), MOCK_ADMIN_USERNAME)
    const pwd = screen.getByTestId('login-password-input')

    // 5번째 실패에서 ACCOUNT_LOCKED
    for (let i = 0; i < 5; i++) {
      await user.clear(pwd)
      await user.type(pwd, `bad${i}0`)
      await user.click(screen.getByTestId('login-submit-button'))
    }

    await waitFor(() => {
      expect((screen.getByTestId('login-submit-button') as HTMLButtonElement).disabled).toBe(true)
    })
    expect(screen.getByTestId('login-error').textContent).toContain('다시 시도해주세요')
  })

  it('redirects to the dashboard on success (default from)', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginRoutes />, { wrapper: wrap, route: '/admin/login' })

    await user.type(screen.getByTestId('login-store-input'), MOCK_STORE_ID)
    await user.type(screen.getByTestId('login-username-input'), MOCK_ADMIN_USERNAME)
    await user.type(screen.getByTestId('login-password-input'), MOCK_ADMIN_PASSWORD)
    await user.click(screen.getByTestId('login-submit-button'))

    await waitFor(() => expect(screen.getByTestId('dashboard-page')).toBeTruthy())
  })
})
