import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from '../../mocks/seed'
import { TableAuthProvider } from '../auth/TableAuthProvider'
import { CartProvider } from '../cart/CartProvider'
import { TABLE_CREDENTIALS_KEY } from '../auth/storage'
import { PENDING_ORDER_KEY, readPendingOrder } from '../cart/storage'
import { MenuPage } from './MenuPage'

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

function renderMenu(harness?: TestHarness) {
  return renderWithProviders(
    <Routes>
      <Route path="/customer/menu" element={<MenuPage />} />
      <Route
        path="/customer/order-complete"
        element={<OrderCompleteStub />}
      />
    </Routes>,
    { wrapper: wrap, route: '/customer/menu', harness },
  )
}

function OrderCompleteStub() {
  // location.state를 간단히 표시 (실제 페이지는 별도 테스트에서 검증)
  return <div data-testid="order-complete-landed">주문 완료</div>
}

async function adminToken(harness: TestHarness): Promise<string> {
  const res = await harness.client.adminLogin({
    storeId: MOCK_STORE_ID,
    username: MOCK_ADMIN_USERNAME,
    password: MOCK_ADMIN_PASSWORD,
  })
  return res.accessToken
}

describe('MenuPage rendering', () => {
  it('카테고리와 메뉴를 렌더링한다', async () => {
    storeCreds()
    renderMenu()
    expect(await screen.findByTestId('menu-page')).toBeInTheDocument()
    expect(screen.getByTestId('category-sidebar-item-메인')).toBeInTheDocument()
    expect(screen.getByTestId('menu-card-1')).toBeInTheDocument()
    // 김치찌개 id1
    expect(within(screen.getByTestId('menu-card-1')).getByText('김치찌개')).toBeInTheDocument()
  })

  it('담기하면 합계가 갱신된다', async () => {
    storeCreds()
    renderMenu()
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1')) // 김치찌개 9000
    await waitFor(() => expect(screen.getByTestId('cart-panel-total')).toHaveTextContent('9,000원'))
    await userEvent.click(screen.getByTestId('menu-card-add-button-6')) // 공기밥 1000
    await waitFor(() => expect(screen.getByTestId('cart-panel-total')).toHaveTextContent('10,000원'))
  })

  it('20개 초과 시 최대 수량 안내 토스트를 보여주고 + 버튼을 비활성화한다', async () => {
    storeCreds()
    renderMenu()
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-6')) // 1개
    const inc = screen.getByTestId('cart-panel-increase-button-6')
    for (let i = 0; i < 19; i++) {
      // 2..20
      await userEvent.click(inc)
    }
    await waitFor(() => expect(screen.getByTestId('cart-panel-quantity-6')).toHaveTextContent('20'))
    expect(screen.getByTestId('cart-panel-increase-button-6')).toBeDisabled()
    // 다시 담기로 최대 안내 토스트
    await userEvent.click(screen.getByTestId('menu-card-add-button-6'))
    await waitFor(() =>
      expect(screen.getByText('한 메뉴는 최대 20개까지 담을 수 있어요.')).toBeInTheDocument(),
    )
  })
})

describe('order flow', () => {
  it('주문 성공: 완료 화면으로 이동하고 장바구니를 비운다', async () => {
    storeCreds()
    renderMenu()
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1'))
    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))

    await waitFor(() => expect(screen.getByTestId('order-complete-landed')).toBeInTheDocument())
  })

  it('주문 실패(네트워크)는 장바구니를 유지하고 모달에 오류를 표시한다', async () => {
    storeCreds()
    const harness = createTestHarness()
    let failOrder = false
    // createOrder만 실패하도록: 전역 forcedError는 쓸 수 없으니 백엔드를 감싼다.
    const origCreate = harness.client.createOrder
    harness.client.createOrder = async (req) => {
      if (failOrder) {
        const { networkError } = await import('../../shared/api/errors')
        throw networkError()
      }
      return origCreate(req)
    }

    renderMenu(harness)
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1'))
    failOrder = true
    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))

    await waitFor(() => expect(screen.getByTestId('order-confirm-error')).toBeInTheDocument())
    // 장바구니는 유지
    expect(screen.getByTestId('cart-panel-item-1')).toBeInTheDocument()
  })

  it('PRICE_CHANGED: 가격 갱신 후 다시 주문하면 성공한다', async () => {
    storeCreds()
    const harness = createTestHarness()
    renderMenu(harness)
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1')) // 김치찌개 9000

    // 담은 뒤 관리자가 가격을 변경한다.
    const token = await adminToken(harness)
    // authBridge admin 토큰 공급 없이 직접 updateMenu 호출: 토큰 인자를 받는 백엔드를 직접 쓴다.
    harness.backend.updateMenu(token, 1, {
      name: '김치찌개',
      price: 9500,
      description: '',
      category: '메인',
      imageUrl: null,
    })

    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))

    await waitFor(() =>
      expect(screen.getByTestId('order-confirm-refresh-prices-button')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('order-confirm-refresh-prices-button'))
    // 소계가 9500으로 갱신
    await waitFor(() => expect(screen.getByTestId('order-confirm-total')).toHaveTextContent('9,500원'))
    // 다시 주문 -> 성공
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))
    await waitFor(() => expect(screen.getByTestId('order-complete-landed')).toBeInTheDocument())
  })

  it('MENU_UNAVAILABLE: 메뉴 제거 버튼으로 제거한다', async () => {
    storeCreds()
    const harness = createTestHarness()
    renderMenu(harness)
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1'))
    await userEvent.click(screen.getByTestId('menu-card-add-button-6'))

    // 관리자가 메뉴1을 삭제한다 -> 주문 시 MENU_UNAVAILABLE
    const token = await adminToken(harness)
    harness.backend.deleteMenu(token, 1)

    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))

    await waitFor(() =>
      expect(screen.getByTestId('order-confirm-remove-unavailable-button')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('order-confirm-unavailable-names').textContent).toContain('김치찌개')
    await userEvent.click(screen.getByTestId('order-confirm-remove-unavailable-button'))
    // 남은 항목(공기밥)이 있으므로 모달이 닫힌다
    await waitFor(() => expect(screen.queryByTestId('order-confirm-modal')).not.toBeInTheDocument())
    expect(screen.queryByTestId('cart-panel-item-1')).not.toBeInTheDocument()
    expect(screen.getByTestId('cart-panel-item-6')).toBeInTheDocument()
  })

  it('멱등 재시도: 같은 clientOrderId를 재사용한다', async () => {
    storeCreds()
    const harness = createTestHarness()
    let failOnce = true
    const origCreate = harness.client.createOrder
    const seenIds: string[] = []
    harness.client.createOrder = async (req) => {
      seenIds.push(req.clientOrderId)
      if (failOnce) {
        failOnce = false
        const { networkError } = await import('../../shared/api/errors')
        throw networkError()
      }
      return origCreate(req)
    }

    renderMenu(harness)
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1'))
    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))
    await waitFor(() => expect(screen.getByTestId('order-confirm-error')).toBeInTheDocument())
    // 재시도
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))
    await waitFor(() => expect(screen.getByTestId('order-complete-landed')).toBeInTheDocument())

    expect(seenIds).toHaveLength(2)
    expect(seenIds[0]).toBe(seenIds[1])
  })

  it('pendingOrder: 주문 성공 시 삭제된다', async () => {
    storeCreds()
    renderMenu()
    await screen.findByTestId('menu-page')
    await userEvent.click(screen.getByTestId('menu-card-add-button-1'))
    await userEvent.click(screen.getByTestId('cart-panel-order-button'))
    await screen.findByTestId('order-confirm-modal')
    // 모달 열림 시 pendingOrder가 기록된다
    await waitFor(() => expect(readPendingOrder()).not.toBeNull())
    await userEvent.click(screen.getByTestId('order-confirm-submit-button'))
    await waitFor(() => expect(screen.getByTestId('order-complete-landed')).toBeInTheDocument())
    expect(localStorage.getItem(PENDING_ORDER_KEY)).toBeNull()
  })
})
