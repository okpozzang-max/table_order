import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import { TableManagementPage } from './TableManagementPage'
import { adminRealtimeWrapper, seedAdminToken } from '../__testutils__/adminTestUtils'

describe('TableManagementPage', () => {
  it('lists seeded tables with status', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<TableManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('table-list-row-1')).toBeTruthy())
    expect(screen.getByTestId('table-list-status-1').textContent).toBe('비어 있음')
  })

  it('registers a new table and shows a success toast', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<TableManagementPage />, { harness, wrapper: adminRealtimeWrapper })

    await user.type(screen.getByTestId('table-register-number-input'), '9')
    await user.type(screen.getByTestId('table-register-password-input'), '4321')
    await user.click(screen.getByTestId('table-register-submit-button'))

    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(screen.getByTestId('table-list-row-6')).toBeTruthy())
  })

  it('shows a duplicate error for an existing table number', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<TableManagementPage />, { harness, wrapper: adminRealtimeWrapper })

    await user.type(screen.getByTestId('table-register-number-input'), '1')
    await user.type(screen.getByTestId('table-register-password-input'), '4321')
    await user.click(screen.getByTestId('table-register-submit-button'))

    await waitFor(() =>
      expect(screen.getByTestId('table-register-number-field-error').textContent).toContain('이미 등록된'),
    )
  })

  it('shows client validation errors for a bad password', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<TableManagementPage />, { harness, wrapper: adminRealtimeWrapper })

    await user.type(screen.getByTestId('table-register-number-input'), '9')
    await user.type(screen.getByTestId('table-register-password-input'), '12')
    await user.click(screen.getByTestId('table-register-submit-button'))

    expect(screen.getByTestId('table-register-password-field-error')).toBeTruthy()
  })
})
