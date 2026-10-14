import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { DashboardPage } from '../pages/DashboardPage'
import { adminRealtimeWrapper, customerToken, seedAdminToken } from '../__testutils__/adminTestUtils'

function createOrder(harness: TestHarness, tableNumber: number): void {
  const token = customerToken(harness, tableNumber)
  harness.backend.createOrder(token, {
    clientOrderId: `co-${Math.random()}`,
    items: [{ menuId: 1, quantity: 1 }],
    clientTotal: 9000,
  })
}

describe('End session flow (TableCard)', () => {
  it('ends the session via confirm and the card total becomes 0 with an empty state', async () => {
    const harness = createTestHarness()
    createOrder(harness, 1)
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })

    await waitFor(() => expect(screen.getByTestId('table-card-total-1').textContent).toContain('9,000원'))

    const endBtn = screen.getByTestId('table-card-end-session-button-1') as HTMLButtonElement
    expect(endBtn.disabled).toBe(false)
    await user.click(endBtn)

    // 확인 팝업
    await waitFor(() => expect(screen.getByTestId('table-card-end-session-confirm-1')).toBeTruthy())
    await user.click(screen.getByTestId('table-card-end-session-confirm-1-confirm-button'))

    // 성공 토스트 + 합계 0 + 빈 상태
    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(screen.getByTestId('table-card-total-1').textContent).toContain('0원'))
    await waitFor(() => {
      const card = screen.getByTestId('table-card-1')
      expect(within(card).getByTestId('table-card-empty-1')).toBeTruthy()
    })
    // 세션이 끝났으므로 이용 완료 버튼은 비활성
    await waitFor(() =>
      expect((screen.getByTestId('table-card-end-session-button-1') as HTMLButtonElement).disabled).toBe(true),
    )
  })

  it('disables the end-session button for an empty table', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() =>
      expect((screen.getByTestId('table-card-end-session-button-1') as HTMLButtonElement).disabled).toBe(true),
    )
  })
})
