// Auth
export { AdminAuthProvider, useAdminAuth } from './auth/AdminAuthProvider'
export type { AdminAuth } from './auth/AdminAuthProvider'
export {
  ADMIN_AUTH_STORAGE_KEY,
  readAdminAuth,
  writeAdminAuth,
  clearAdminAuth,
} from './auth/storage'
export type { AdminAuthRecord } from './auth/storage'

// Realtime
export { AdminRealtimeProvider, useAdminRealtime } from './realtime/AdminRealtimeProvider'
export type { AdminRealtime } from './realtime/AdminRealtimeProvider'

// Layout + pages (routed by the app shell)
export { AdminLayout } from './components/AdminLayout'
export { LoginPage } from './pages/LoginPage'
export { DashboardPage } from './pages/DashboardPage'
export { TableManagementPage } from './pages/TableManagementPage'
export { MenuManagementPage } from './pages/MenuManagementPage'

// Components (reusable)
export { ConnectionIndicator } from './components/ConnectionIndicator'
export { TableCard } from './components/TableCard'
export { OrderRow } from './components/OrderRow'
export { OrderDetailModal } from './components/OrderDetailModal'
export { TableHistoryModal } from './components/TableHistoryModal'
export { TableRegisterForm } from './components/TableRegisterForm'
export { MenuForm } from './components/MenuForm'
export { MenuListByCategory } from './components/MenuListByCategory'

// Hooks + query keys
export * from './hooks/useAdminQueries'
