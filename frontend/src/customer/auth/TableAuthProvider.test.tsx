import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { TestHarness } from '../../test/renderWithProviders'
import { authBridge } from '../../shared/api/authBridge'
import { MockBackend } from '../../mocks/mockBackend'
import { createMockClient } from '../../mocks/mockClient'
import { MOCK_STORE_ID, MOCK_TABLE_PASSWORD } from '../../mocks/seed'
import { TableAuthProvider, useTableAuth } from './TableAuthProvider'
import { TABLE_CREDENTIALS_KEY } from './storage'

function Probe() {
  const { status, tableNumber, errorMessage, prefill } = useTableAuth()
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="tableNumber">{tableNumber ?? ''}</span>
      <span data-testid="errorMessage">{errorMessage ?? ''}</span>
      <span data-testid="prefill">{prefill ? `${prefill.storeId}:${prefill.tableNumber}` : ''}</span>
    </div>
  )
}

function wrap(ui: ReactElement) {
  return <TableAuthProvider>{ui}</TableAuthProvider>
}

function storeCreds(storeId: string, tableNumber: number, password: string) {
  localStorage.setItem(TABLE_CREDENTIALS_KEY, JSON.stringify({ storeId, tableNumber, password }))
}

/** forcedError 함수를 외부에서 제어할 수 있는 harness. */
function controllableHarness(forced: () => 'network' | 'server' | null): TestHarness {
  const backend = new MockBackend({})
  const client = createMockClient(backend, { delay: () => 0, forcedError: forced })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  })
  return { backend, client, queryClient }
}

describe('TableAuthProvider', () => {
  it('자격 증명이 없으면 needs_setup', async () => {
    renderWithProviders(<Probe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('needs_setup'))
  })

  it('유효한 자격 증명이면 authenticated + tableNumber 설정', async () => {
    storeCreds(MOCK_STORE_ID, 3, MOCK_TABLE_PASSWORD)
    renderWithProviders(<Probe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
    expect(screen.getByTestId('tableNumber')).toHaveTextContent('3')
    expect(authBridge.getTableToken()).toBeTruthy()
  })

  it('잘못된 자격 증명이면 needs_setup + prefill(비밀번호 제외) + 오류 메시지', async () => {
    storeCreds(MOCK_STORE_ID, 3, '9999')
    renderWithProviders(<Probe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('needs_setup'))
    expect(screen.getByTestId('prefill')).toHaveTextContent(`${MOCK_STORE_ID}:3`)
    expect(screen.getByTestId('errorMessage').textContent).toContain('로그인 정보가 맞지 않아요')
  })

  it('네트워크 오류이면 error 상태 + 수동 재시도로 복구', async () => {
    storeCreds(MOCK_STORE_ID, 3, MOCK_TABLE_PASSWORD)
    let fail = true
    const harness = controllableHarness(() => (fail ? 'network' : null))

    function RetryProbe() {
      const { status, retry } = useTableAuth()
      return (
        <div>
          <span data-testid="status">{status}</span>
          <button onClick={retry} data-testid="retry">
            retry
          </button>
        </div>
      )
    }

    renderWithProviders(<RetryProbe />, { wrapper: wrap, harness })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('error'))
    fail = false
    await userEvent.click(screen.getByTestId('retry'))
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
  })

  it('UNAUTHORIZED 시 저장된 자격 증명으로 재로그인한다 (handleTableUnauthorized)', async () => {
    storeCreds(MOCK_STORE_ID, 3, MOCK_TABLE_PASSWORD)
    renderWithProviders(<Probe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
    const ok = await authBridge.handleTableUnauthorized()
    expect(ok).toBe(true)
    expect(authBridge.getTableToken()).toBeTruthy()
  })

  it('자격 증명이 사라진 상태에서 UNAUTHORIZED면 false + needs_setup', async () => {
    storeCreds(MOCK_STORE_ID, 3, MOCK_TABLE_PASSWORD)
    renderWithProviders(<Probe />, { wrapper: wrap })
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authenticated'))
    localStorage.removeItem(TABLE_CREDENTIALS_KEY)
    const ok = await authBridge.handleTableUnauthorized()
    expect(ok).toBe(false)
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('needs_setup'))
  })
})
