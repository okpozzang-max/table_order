import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { DashboardPage } from './DashboardPage'
import { adminRealtimeWrapper, customerToken, seedAdminToken } from '../__testutils__/adminTestUtils'

/** 테이블 N에 주문을 size개 생성한다. 각 주문은 김치찌개(id1, 9000원) 1개. */
function createOrders(harness: TestHarness, tableNumber: number, count: number): void {
  const token = customerToken(harness, tableNumber)
  for (let i = 0; i < count; i++) {
    harness.backend.createOrder(token, {
      clientOrderId: `co-${tableNumber}-${i}-${Math.random()}`,
      items: [{ menuId: 1, quantity: 1 }],
      clientTotal: 9000,
    })
  }
}

describe('DashboardPage', () => {
  it('renders table cards in ascending table order', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })

    await waitFor(() => expect(screen.getByTestId('table-card-1')).toBeTruthy())
    const cards = screen.getAllByTestId(/^table-card-\d+$/)
    const ids = cards.map((c) => Number(c.getAttribute('data-testid')!.replace('table-card-', '')))
    expect(ids).toEqual([...ids].sort((a, b) => a - b))
    expect(ids).toContain(1)
    expect(ids).toContain(5)
  })

  it('shows only the latest 3 orders in the unfiltered preview', async () => {
    const harness = createTestHarness()
    createOrders(harness, 1, 5)
    seedAdminToken(harness)
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })

    await waitFor(() => expect(screen.getByTestId('table-card-1')).toBeTruthy())
    await waitFor(() => {
      const card = screen.getByTestId('table-card-1')
      expect(within(card).getAllByTestId(/^order-row-\d+$/).length).toBe(3)
    })
    // 총 주문액 = 5 x 9000
    expect(screen.getByTestId('table-card-total-1').textContent).toContain('45,000원')
    expect(screen.getByTestId('table-card-count-1').textContent).toContain('5')
  })

  it('shows all orders of a table when the filter is active', async () => {
    const harness = createTestHarness()
    createOrders(harness, 1, 5)
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })

    await waitFor(() => expect(screen.getByTestId('table-card-1')).toBeTruthy())
    await user.selectOptions(screen.getByTestId('dashboard-table-filter'), '1')

    await waitFor(() => {
      const card = screen.getByTestId('table-card-1')
      expect(within(card).getAllByTestId(/^order-row-\d+$/).length).toBe(5)
    })
    // 다른 테이블 카드는 숨겨진다
    expect(screen.queryByTestId('table-card-2')).toBeNull()
  })

  it('highlights a table on order_created and clears it on markSeen (header click)', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, { harness, wrapper: adminRealtimeWrapper })

    await waitFor(() => expect(screen.getByTestId('table-card-1')).toBeTruthy())

    // 백엔드에서 주문 생성 -> order_created 이벤트 발행 -> 카드 강조 + 재조회
    createOrders(harness, 1, 1)

    await waitFor(() => {
      expect(screen.getByTestId('table-card-1').getAttribute('data-highlighted')).toBe('true')
    })

    await user.click(screen.getByTestId('table-card-header-1'))
    await waitFor(() => {
      expect(screen.getByTestId('table-card-1').getAttribute('data-highlighted')).toBeNull()
    })
  })
})
