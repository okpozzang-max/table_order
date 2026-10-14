import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import type { ReactElement } from 'react'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from '../../mocks/seed'
import { TableAuthProvider } from '../auth/TableAuthProvider'
import { TABLE_CREDENTIALS_KEY } from '../auth/storage'
import { TableSetupPage } from './TableSetupPage'

function wrap(ui: ReactElement) {
  return <TableAuthProvider>{ui}</TableAuthProvider>
}

function renderSetup() {
  return renderWithProviders(
    <Routes>
      <Route path="/customer/setup" element={<TableSetupPage />} />
      <Route path="/customer/menu" element={<div data-testid="menu-landed">메뉴</div>} />
    </Routes>,
    { wrapper: wrap, route: '/customer/setup' },
  )
}

describe('TableSetupPage', () => {
  it('빈 제출은 필드 오류를 보여준다', async () => {
    renderSetup()
    await userEvent.click(await screen.findByTestId('table-setup-submit-button'))
    expect(screen.getByTestId('table-setup-field-storeId-error')).toBeInTheDocument()
    expect(screen.getByTestId('table-setup-field-tableNumber-error')).toBeInTheDocument()
    expect(screen.getByTestId('table-setup-field-password-error')).toBeInTheDocument()
  })

  it('성공하면 자격 증명을 저장하고 메뉴로 이동한다', async () => {
    renderSetup()
    await userEvent.type(screen.getByTestId('table-setup-input-storeId'), MOCK_STORE_ID)
    await userEvent.type(screen.getByTestId('table-setup-input-tableNumber'), '2')
    await userEvent.type(screen.getByTestId('table-setup-input-password'), MOCK_TABLE_PASSWORD)
    await userEvent.click(screen.getByTestId('table-setup-submit-button'))

    await waitFor(() => expect(screen.getByTestId('menu-landed')).toBeInTheDocument())
    const stored = JSON.parse(localStorage.getItem(TABLE_CREDENTIALS_KEY) as string)
    expect(stored).toMatchObject({ storeId: MOCK_STORE_ID, tableNumber: 2, password: MOCK_TABLE_PASSWORD })
  })

  it('잘못된 비밀번호면 서버 오류를 표시하고 자격 증명을 저장하지 않는다', async () => {
    renderSetup()
    await userEvent.type(screen.getByTestId('table-setup-input-storeId'), MOCK_STORE_ID)
    await userEvent.type(screen.getByTestId('table-setup-input-tableNumber'), '2')
    await userEvent.type(screen.getByTestId('table-setup-input-password'), '0000')
    await userEvent.click(screen.getByTestId('table-setup-submit-button'))

    await waitFor(() =>
      expect(screen.getByTestId('table-setup-server-error').textContent).toContain('로그인 정보가 맞지 않아요'),
    )
    expect(localStorage.getItem(TABLE_CREDENTIALS_KEY)).toBeNull()
  })
})
