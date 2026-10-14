import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { AppStateProviders } from './App'
import { AppRoutes } from './AppRoutes'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from '../mocks/seed'
import type { TestHarness } from '../test/renderWithProviders'

function renderApp(route: string, harness?: TestHarness) {
  return renderWithProviders(<AppRoutes />, {
    route,
    harness,
    wrapper: (ui) => <AppStateProviders>{ui}</AppStateProviders>,
  })
}

async function adminLogin(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByTestId('login-store-input'), MOCK_STORE_ID)
  await user.type(screen.getByTestId('login-username-input'), MOCK_ADMIN_USERNAME)
  await user.type(screen.getByTestId('login-password-input'), MOCK_ADMIN_PASSWORD)
  await user.click(screen.getByTestId('login-submit-button'))
}

describe('App 라우팅과 가드', () => {
  it('저장된 자격 증명이 없으면 고객 메뉴 접근 시 초기 설정 화면으로 이동한다', async () => {
    renderApp('/customer/menu')
    expect(await screen.findByTestId('table-setup-page')).toBeInTheDocument()
  })

  it('저장된 자격 증명이 있으면 자동 로그인되어 메뉴 화면이 보인다 (US-C1.1)', async () => {
    localStorage.setItem(
      'tableorder.table.credentials',
      JSON.stringify({ storeId: MOCK_STORE_ID, tableNumber: 1, password: MOCK_TABLE_PASSWORD }),
    )
    renderApp('/customer')
    expect(await screen.findByTestId('menu-page')).toBeInTheDocument()
    expect(await screen.findByText('김치찌개')).toBeInTheDocument()
  })

  it('미인증 관리자는 로그인 화면으로 이동하고, 로그인 후 원래 경로로 돌아온다 (US-E9)', async () => {
    const user = userEvent.setup()
    renderApp('/admin/tables')
    await adminLogin(user)
    expect(await screen.findByTestId('table-register-form')).toBeInTheDocument()
  })

  it('알 수 없는 경로는 안내 화면을 보여준다', async () => {
    renderApp('/nope')
    expect(await screen.findByTestId('not-found-page')).toBeInTheDocument()
  })
})

describe('고객 주문 흐름 (통합)', () => {
  it('초기 설정 -> 메뉴 담기 -> 주문 확정 -> 주문 번호 표시', async () => {
    const user = userEvent.setup()
    renderApp('/customer/menu')

    await user.type(await screen.findByTestId('table-setup-input-storeId'), MOCK_STORE_ID)
    await user.type(screen.getByTestId('table-setup-input-tableNumber'), '1')
    await user.type(screen.getByTestId('table-setup-input-password'), MOCK_TABLE_PASSWORD)
    await user.click(screen.getByTestId('table-setup-submit-button'))

    await user.click(await screen.findByTestId('menu-card-add-button-1'))
    await user.click(screen.getByTestId('menu-card-add-button-1'))
    await user.click(screen.getByTestId('cart-panel-order-button'))
    await user.click(await screen.findByTestId('order-confirm-submit-button'))

    const number = await screen.findByTestId('order-complete-number')
    expect(number).toHaveTextContent('0001')
    // 자격 증명이 저장되었다
    expect(localStorage.getItem('tableorder.table.credentials')).not.toBeNull()
  })
})

describe('고객 주문 -> 관리자 대시보드 (통합)', () => {
  it('고객이 주문하면 관리자 대시보드에 반영되고 강조된다 (US-A2.1, A2.2)', async () => {
    const user = userEvent.setup()
    const { backend } = renderApp('/admin/dashboard')
    await adminLogin(user)

    const header = await screen.findByTestId('table-card-header-1')
    expect(header).toBeInTheDocument()

    // 다른 기기의 고객 주문을 백엔드에 직접 생성
    const token = backend.customerLogin({
      storeId: MOCK_STORE_ID,
      tableNumber: 1,
      password: MOCK_TABLE_PASSWORD,
    }).accessToken
    await act(async () => {
      backend.createOrder(token, {
        clientOrderId: crypto.randomUUID(),
        items: [{ menuId: 1, quantity: 2 }],
        clientTotal: 18000,
      })
    })

    const row = await screen.findByTestId('order-row-1')
    expect(within(row).getByText('18,000원')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('table-card-1')).toHaveAttribute('data-highlighted', 'true'))

    // 확인(클릭)하면 강조가 해제된다
    await user.click(screen.getByTestId('table-card-header-1'))
    await waitFor(() => expect(screen.getByTestId('table-card-1')).not.toHaveAttribute('data-highlighted'))
  })
})
