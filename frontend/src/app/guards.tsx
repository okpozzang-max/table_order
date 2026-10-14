import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { TableAuthErrorScreen, TableAuthLoadingScreen, useTableAuth } from '../customer'
import { useAdminAuth } from '../admin'

/** 고객 보호 경로: 인증 상태에 따라 로딩/오류/설정 화면으로 보낸다. */
export function CustomerGuard() {
  const { status } = useTableAuth()
  if (status === 'loading') return <TableAuthLoadingScreen />
  if (status === 'error') return <TableAuthErrorScreen />
  if (status === 'needs_setup') return <Navigate to="/customer/setup" replace />
  return <Outlet />
}

/** 관리자 보호 경로: 비인증이면 로그인 화면으로 보내고 원래 경로를 기억한다. */
export function AdminGuard() {
  const { isAuthenticated } = useAdminAuth()
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
