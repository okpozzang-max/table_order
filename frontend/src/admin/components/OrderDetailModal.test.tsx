import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { OrderDetailModal } from './OrderDetailModal'
import { adminAuthWrapper, customerToken, seedAdminToken } from '../__testutils__/adminTestUtils'

function makeOrder(harness: TestHarness, tableNumber = 1): number {
  const token = customerToken(harness, tableNumber)
  const order = harness.backend.createOrder(token, {
    clientOrderId: `co-${Math.random()}`,
    items: [{ menuId: 1, quantity: 2 }],
    clientTotal: 18000,
  })
  return order.id
}

describe('OrderDetailModal', () => {
  it('walks the status sequence PENDING -> PREPARING -> COMPLETED then hides the button', async () => {
    const harness = createTestHarness()
    const orderId = makeOrder(harness)
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<OrderDetailModal orderId={orderId} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })

    // PENDING -> '준비 시작'
    await waitFor(() => expect(screen.getByTestId('order-detail-next-step-button').textContent).toBe('준비 시작'))
    await user.click(screen.getByTestId('order-detail-next-step-button'))

    // PREPARING -> '완료 처리'
    await waitFor(() => expect(screen.getByTestId('order-detail-next-step-button').textContent).toBe('완료 처리'))
    await user.click(screen.getByTestId('order-detail-next-step-button'))

    // COMPLETED -> 버튼 없음
    await waitFor(() => expect(screen.queryByTestId('order-detail-next-step-button')).toBeNull())
  })

  it('shows total and items', async () => {
    const harness = createTestHarness()
    const orderId = makeOrder(harness)
    seedAdminToken(harness)
    renderWithProviders(<OrderDetailModal orderId={orderId} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })
    await waitFor(() => expect(screen.getByTestId('order-detail-total').textContent).toContain('18,000원'))
    expect(screen.getByTestId('order-detail-item-1')).toBeTruthy()
  })

  it('handles INVALID_TRANSITION by toasting and refetching', async () => {
    const harness = createTestHarness()
    const orderId = makeOrder(harness)
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<OrderDetailModal orderId={orderId} onClose={() => {}} />, {
      harness,
      wrapper: adminAuthWrapper,
    })
    await waitFor(() => expect(screen.getByTestId('order-detail-next-step-button')).toBeTruthy())

    // 백엔드에서 먼저 상태를 PREPARING으로 바꿔두면, PENDING->PREPARING 요청이 INVALID_TRANSITION
    const adminToken = harness.backend.adminLogin({
      storeId: 'demo',
      username: 'admin',
      password: 'admin1234',
    }).accessToken
    harness.backend.changeOrderStatus(adminToken, orderId, 'PREPARING')

    await user.click(screen.getByTestId('order-detail-next-step-button'))

    await waitFor(() => expect(screen.getByTestId('toast-error')).toBeTruthy())
    // 재조회로 최신 상태(PREPARING)의 다음 버튼이 '완료 처리'가 된다
    await waitFor(() => expect(screen.getByTestId('order-detail-next-step-button').textContent).toBe('완료 처리'))
  })

  it('deletes an order after confirm and calls onClose', async () => {
    const harness = createTestHarness()
    const orderId = makeOrder(harness)
    seedAdminToken(harness)
    const user = userEvent.setup()
    let closed = false
    renderWithProviders(
      <OrderDetailModal orderId={orderId} onClose={() => {
        closed = true
      }} />,
      { harness, wrapper: adminAuthWrapper },
    )
    await waitFor(() => expect(screen.getByTestId('order-detail-delete-button')).toBeTruthy())
    await user.click(screen.getByTestId('order-detail-delete-button'))

    await waitFor(() => expect(screen.getByTestId('order-detail-delete-confirm')).toBeTruthy())
    await user.click(screen.getByTestId('order-detail-delete-confirm-confirm-button'))

    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(closed).toBe(true))
  })
})
