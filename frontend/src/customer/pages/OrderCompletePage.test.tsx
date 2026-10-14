import { describe, expect, it, vi, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { OrderCompletePage } from './OrderCompletePage'

function renderComplete(state: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/customer/order-complete', state }]}>
      <Routes>
        <Route path="/customer/order-complete" element={<OrderCompletePage />} />
        <Route path="/customer/menu" element={<div data-testid="menu-landed">메뉴</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.useRealTimers()
})

describe('OrderCompletePage', () => {
  it('주문 번호를 표시한다', () => {
    renderComplete({ orderNumber: '0007' })
    expect(screen.getByTestId('order-complete-number')).toHaveTextContent('0007')
  })

  it('주문 번호 상태가 없으면 메뉴로 리다이렉트한다', () => {
    renderComplete(undefined)
    expect(screen.getByTestId('menu-landed')).toBeInTheDocument()
  })

  it('"바로 메뉴로 이동" 버튼으로 즉시 이동한다', async () => {
    renderComplete({ orderNumber: '0007' })
    await userEvent.click(screen.getByTestId('order-complete-go-menu-button'))
    expect(screen.getByTestId('menu-landed')).toBeInTheDocument()
  })

  it('5초 카운트다운 후 자동으로 메뉴로 이동한다', async () => {
    vi.useFakeTimers()
    try {
      renderComplete({ orderNumber: '0007' })
      expect(screen.getByTestId('order-complete-countdown')).toHaveTextContent('5초')
      act(() => {
        vi.advanceTimersByTime(5000)
      })
      expect(screen.getByTestId('menu-landed')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
