import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, createTestHarness } from '../../test/renderWithProviders'
import { MenuManagementPage } from './MenuManagementPage'
import { adminRealtimeWrapper, seedAdminToken } from '../__testutils__/adminTestUtils'

describe('MenuManagementPage', () => {
  it('renders seeded menus grouped by category', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-row-1')).toBeTruthy())
    expect(screen.getByTestId('menu-category-메인')).toBeTruthy()
  })

  it('shows validation errors when creating with an invalid price', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-row-1')).toBeTruthy())

    await user.click(screen.getByTestId('menu-create-button'))
    await user.type(screen.getByTestId('menu-form-name-input'), '새메뉴')
    await user.type(screen.getByTestId('menu-form-price-input'), '10') // < 100
    await user.type(screen.getByTestId('menu-form-category-input'), '메인')
    await user.click(screen.getByTestId('menu-form-submit-button'))

    expect(screen.getByTestId('menu-form-price-field-error')).toBeTruthy()
  })

  it('creates a new menu', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-row-1')).toBeTruthy())

    await user.click(screen.getByTestId('menu-create-button'))
    await user.type(screen.getByTestId('menu-form-name-input'), '새치즈볶음')
    await user.type(screen.getByTestId('menu-form-price-input'), '12000')
    await user.type(screen.getByTestId('menu-form-category-input'), '메인')
    await user.click(screen.getByTestId('menu-form-submit-button'))

    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('새치즈볶음')).toBeTruthy())
  })

  it('edits an existing menu', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-row-1')).toBeTruthy())

    await user.click(screen.getByTestId('menu-row-edit-button-1'))
    const nameInput = screen.getByTestId('menu-form-name-input') as HTMLInputElement
    expect(nameInput.value).toBe('김치찌개')
    await user.clear(nameInput)
    await user.type(nameInput, '묵은지김치찌개')
    await user.click(screen.getByTestId('menu-form-submit-button'))

    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('묵은지김치찌개')).toBeTruthy())
  })

  it('deletes a menu after confirm', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-row-1')).toBeTruthy())

    await user.click(screen.getByTestId('menu-row-delete-button-1'))
    await waitFor(() => expect(screen.getByTestId('menu-delete-confirm')).toBeTruthy())
    await user.click(screen.getByTestId('menu-delete-confirm-confirm-button'))

    await waitFor(() => expect(screen.getByTestId('toast-success')).toBeTruthy())
    await waitFor(() => expect(screen.queryByTestId('menu-row-1')).toBeNull())
  })

  it('disables move-up on the first row and move-down on the last row within a category', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-category-메인')).toBeTruthy())

    // '메인' 카테고리: id 1,2,3,4 (김치찌개, 된장찌개, 제육볶음, 비빔밥)
    expect((screen.getByTestId('menu-row-move-up-button-1') as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByTestId('menu-row-move-down-button-1') as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByTestId('menu-row-move-down-button-4') as HTMLButtonElement).disabled).toBe(true)
  })

  it('persists reorder when moving a menu down', async () => {
    const harness = createTestHarness()
    seedAdminToken(harness)
    const user = userEvent.setup()
    renderWithProviders(<MenuManagementPage />, { harness, wrapper: adminRealtimeWrapper })
    await waitFor(() => expect(screen.getByTestId('menu-category-메인')).toBeTruthy())

    // 첫 행(김치찌개 id1)을 아래로 이동
    await user.click(screen.getByTestId('menu-row-move-down-button-1'))

    // 재조회 후 '메인' 카테고리 첫 행이 된장찌개(id2)가 된다
    await waitFor(() => {
      const cat = screen.getByTestId('menu-category-메인')
      const rows = within(cat).getAllByTestId(/^menu-row-\d+$/)
      expect(rows[0].getAttribute('data-testid')).toBe('menu-row-2')
    })
  })
})
