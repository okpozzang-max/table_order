import { Link, Navigate, Route, Routes } from 'react-router-dom'
import {
  CustomerLayout,
  MenuPage,
  OrderCompletePage,
  OrderHistoryPage,
  TableSetupPage,
} from '../customer'
import {
  AdminLayout,
  DashboardPage,
  LoginPage,
  MenuManagementPage,
  TableManagementPage,
} from '../admin'
import { AdminGuard, CustomerGuard } from './guards'

function NotFoundPage() {
  return (
    <main style={{ padding: 'var(--space-6)', textAlign: 'center' }} data-testid="not-found-page">
      <h1>페이지를 찾을 수 없어요</h1>
      <p>
        <Link to="/customer" data-testid="not-found-customer-link">
          고객 화면
        </Link>{' '}
        ·{' '}
        <Link to="/admin" data-testid="not-found-admin-link">
          관리자 화면
        </Link>
      </p>
    </main>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/customer" replace />} />

      <Route path="/customer">
        <Route index element={<Navigate to="menu" replace />} />
        <Route path="setup" element={<TableSetupPage />} />
        <Route element={<CustomerGuard />}>
          <Route element={<CustomerLayout />}>
            <Route path="menu" element={<MenuPage />} />
            <Route path="orders" element={<OrderHistoryPage />} />
            <Route path="order-complete" element={<OrderCompletePage />} />
          </Route>
        </Route>
      </Route>

      <Route path="/admin">
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="login" element={<LoginPage />} />
        <Route element={<AdminGuard />}>
          <Route element={<AdminLayout />}>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="tables" element={<TableManagementPage />} />
            <Route path="menus" element={<MenuManagementPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
