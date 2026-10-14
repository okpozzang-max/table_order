import { describe, expect, it, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from '../../mocks/seed'
import { TableAuthProvider } from '../auth/TableAuthProvider'
import { CartProvider } from '../cart/CartProvider'
import { TABLE_CREDENTIALS_KEY } from '../auth/storage'
import { OrderHistoryPage } from './OrderHistoryPage'

function storeCreds(tableNumber = 2) {
  localStorage.setItem(
    TABLE_CREDENTIALS_KEY,
    JSON.stringify({ storeId: MOCK_STORE_ID, tableNumber, password: MOCK_TABLE_PASSWORD }),
  )
}

function wrap(ui: ReactElement) {
  return (
    <TableAuthProvider>
      <CartProvider>{ui}</CartProvider>
    </TableAuthProvider>
  )
}

/** 테이블 토큰을 얻어 지정한 수만큼 주문을 생성한다 (백엔드 직접 호출). */
async function seedOrders(harness: TestHarness, tableNumber: number, count: number): Promise<string> {
  const login = await harness.client.customerLogin({
    storeId: MOCK_STORE_ID,
    tableNumber,
    password: MOCK_TABLE_PASSWORD,
  })
  const token = login.accessToken
  for (let i = 0; i < count; i++) {
    harness.backend.createOrder(token, {
      clientOrderId: `seed-${i}`,
      items: [{ menuId: 6, quantity: 1 }], // 공기밥 1000
      clientTotal: 1000,
    })
  }
  return token
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('OrderHistoryPage', () => {
  it('빈 상태를 보여준다', async () => {
    storeCreds()
    renderWithProviders(<OrderHistoryPage />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('order-history-empty')).toBeInTheDocument())
  })

  it('주문을 최신순으로 보여준다', async () => {
    storeCreds()
    const harness = createTestHarness()
    await seedOrders(harness, 2, 3)
    renderWithProviders(<OrderHistoryPage />, { wrapper: wrap, harness })
    await waitFor(() => expect(screen.getByTestId('order-history-page')).toBeInTheDocument())
    const items = await screen.findAllByText(/주문 #/)
    // 서버는 id 내림차순(최신 먼저) -> #0003, #0002, #0001
    expect(items[0]).toHaveTextContent('0003')
    expect(items[items.length - 1]).toHaveTextContent('0001')
  })

  it('폴링으로 새 주문이 반영된다 (refetch)', async () => {
    storeCreds()
    const harness = createTestHarness()
    const token = await seedOrders(harness, 2, 1)
    const { queryClient } = renderWithProviders(<OrderHistoryPage />, { wrapper: wrap, harness })
    await waitFor(() => expect(screen.getByText(/주문 #0001/)).toBeInTheDocument())

    // 새 주문을 추가하고 쿼리를 무효화(폴링 재조회를 흉내)
    harness.backend.createOrder(token, {
      clientOrderId: 'seed-new',
      items: [{ menuId: 6, quantity: 2 }],
      clientTotal: 2000,
    })
    await queryClient.invalidateQueries({ queryKey: ['customer', 'orders'] })
    await waitFor(() => expect(screen.getByText(/주문 #0002/)).toBeInTheDocument())
  })

  it('무한 스크롤: sentinel이 보이면 다음 페이지를 불러온다', async () => {
    storeCreds()
    const harness = createTestHarness()
    await seedOrders(harness, 2, 15) // 10 + 5 -> 두 페이지

    // IntersectionObserver를 제어 가능한 스텁으로 교체한다.
    const triggerRef: { fn: (() => void) | null } = { fn: null }
    class ControlledIO {
      private cb: IntersectionObserverCallback
      constructor(cb: IntersectionObserverCallback) {
        this.cb = cb
        triggerRef.fn = () =>
          this.cb(
            [{ isIntersecting: true } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver,
          )
      }
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return []
      }
    }
    const originalIO = globalThis.IntersectionObserver
    ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = ControlledIO

    try {
      renderWithProviders(<OrderHistoryPage />, { wrapper: wrap, harness })
      await waitFor(() => expect(screen.getByTestId('order-history-page')).toBeInTheDocument())
      // 첫 페이지 10건
      await waitFor(() => expect(screen.getAllByText(/주문 #/).length).toBe(10))
      // sentinel 교차 -> 다음 페이지
      expect(triggerRef.fn).toBeTypeOf('function')
      triggerRef.fn?.()
      await waitFor(() => expect(screen.getAllByText(/주문 #/).length).toBe(15))
    } finally {
      ;(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = originalIO
    }
  })
})
