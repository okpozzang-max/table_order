import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { TableHistoryModal } from './TableHistoryModal'
import { adminAuthWrapper, customerToken, seedAdminToken } from '../__testutils__/adminTestUtils'

/** 테이블 1에 주문을 만들고 세션을 끝내 과거 내역을 1건 만든다. */
function seedHistory(harness: TestHarness): void {
  const token = customerToken(harness, 1)
  harness.backend.createOrder(token, {
    clientOrderId: `co-${Math.random()}`,
    items: [{ menuId: 1, quantity: 1 }],
    clientTotal: 9000,
  })
  const adminToken = harness.backend.adminLogin({
    storeId: 'demo',
    username: 'admin',
    password: 'admin1234',
  }).accessToken
  harness.backend.endSession(adminToken, 1)
}

describe('TableHistoryModal', () => {
  it('lists past orders', async () => {
    const harness = createTestHarness()
    seedHistory(harness)
    seedAdminToken(harness)
    renderWithProviders(<TableHistoryModal table={{ id: 1, tableNumber: 1 }} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })
    await waitFor(() => expect(screen.getByTestId('table-history-row-1')).toBeTruthy())
    expect(screen.getByTestId('table-history-row-1').textContent).toContain('9,000원')
    expect(screen.getByTestId('table-history-row-1').textContent).toContain('이용 완료 시각')
  })

  it('shows an empty state when there is no history', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<TableHistoryModal table={{ id: 2, tableNumber: 2 }} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })
    await waitFor(() => expect(screen.getByTestId('table-history-empty')).toBeTruthy())
  })

  it('shows a validation error for an invalid date range and does not query', async () => {
    const harness = createTestHarness()
    seedHistory(harness)
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<TableHistoryModal table={{ id: 1, tableNumber: 1 }} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })
    await waitFor(() => expect(screen.getByTestId('table-history-row-1')).toBeTruthy())

    // from > to
    await user.type(screen.getByTestId('table-history-from-input'), '2026-10-20')
    await user.type(screen.getByTestId('table-history-to-input'), '2026-10-10')

    await waitFor(() => expect(screen.getByTestId('table-history-to-field-error')).toBeTruthy())
  })

  it('calls onClose when the close button is clicked', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    let closed = false
    renderWithProviders(
      <TableHistoryModal table={{ id: 1, tableNumber: 1 }} onClose={() => {
        closed = true
      }} />,
      { harness, wrapper: adminAuthWrapper },
    )
    await user.click(screen.getByTestId('table-history-close-button'))
    expect(closed).toBe(true)
  })
})
