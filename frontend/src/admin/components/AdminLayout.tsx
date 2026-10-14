import { NavLink, Outlet } from 'react-router-dom'
import { Button } from '../../shared/ui'
import { AdminRealtimeProvider, useAdminRealtime } from '../realtime/AdminRealtimeProvider'
import { useAdminAuth } from '../auth/AdminAuthProvider'
import { ConnectionIndicator } from './ConnectionIndicator'
import styles from './AdminLayout.module.css'

function LayoutInner() {
  const { status, refreshNow } = useAdminRealtime()
  const { logout } = useAdminAuth()

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <nav className={styles.nav} aria-label="관리자 메뉴">
          <NavLink to="/admin/dashboard" className={navClass} data-testid="admin-nav-dashboard">
            대시보드
          </NavLink>
          <NavLink to="/admin/tables" className={navClass} data-testid="admin-nav-tables">
            테이블 관리
          </NavLink>
          <NavLink to="/admin/menus" className={navClass} data-testid="admin-nav-menus">
            메뉴 관리
          </NavLink>
        </nav>
        <div className={styles.right}>
          <ConnectionIndicator status={status} />
          <Button onClick={refreshNow} data-testid="admin-refresh-button">
            새로고침
          </Button>
          <Button onClick={logout} data-testid="admin-logout-button">
            로그아웃
          </Button>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

export function AdminLayout() {
  return (
    <AdminRealtimeProvider>
      <LayoutInner />
    </AdminRealtimeProvider>
  )
}
