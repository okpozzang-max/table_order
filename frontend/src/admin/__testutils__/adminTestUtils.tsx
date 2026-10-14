import type { ReactElement } from 'react'
import { MOCK_ADMIN_PASSWORD, MOCK_ADMIN_USERNAME, MOCK_STORE_ID } from '../../mocks/seed'
import type { TestHarness } from '../../test/renderWithProviders'
import { writeAdminAuth } from '../auth/storage'
import { AdminAuthProvider } from '../auth/AdminAuthProvider'
import { AdminRealtimeProvider } from '../realtime/AdminRealtimeProvider'

/** 백엔드에서 관리자 토큰을 발급받아 localStorage에 심는다. AdminAuthProvider가 마운트 시 복원한다. */
export function seedAdminToken(harness: TestHarness): void {
  const res = harness.backend.adminLogin({
    storeId: MOCK_STORE_ID,
    username: MOCK_ADMIN_USERNAME,
    password: MOCK_ADMIN_PASSWORD,
  })
  writeAdminAuth({ accessToken: res.accessToken, expiresAt: res.expiresAt })
}

/** 테이블 토큰을 발급받아 반환한다 (주문 생성용). */
export function customerToken(harness: TestHarness, tableNumber = 1): string {
  const res = harness.backend.customerLogin({
    storeId: MOCK_STORE_ID,
    tableNumber,
    password: '1234',
  })
  return res.accessToken
}

/** AdminAuthProvider로 감싸는 wrapper. */
export function adminAuthWrapper(children: ReactElement): ReactElement {
  return <AdminAuthProvider>{children}</AdminAuthProvider>
}

/** AdminAuthProvider + AdminRealtimeProvider로 감싸는 wrapper. */
export function adminRealtimeWrapper(children: ReactElement): ReactElement {
  return (
    <AdminAuthProvider>
      <AdminRealtimeProvider>{children}</AdminRealtimeProvider>
    </AdminAuthProvider>
  )
}
