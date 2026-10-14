import { NavLink, Outlet } from 'react-router-dom'
import { useTableAuth } from './auth/TableAuthProvider'
import styles from './CustomerLayout.module.css'

export function CustomerLayout() {
  const { tableNumber } = useTableAuth()

  const tabClass = ({ isActive }: { isActive: boolean }) =>
    `${styles.tab} ${isActive ? styles.active : ''}`

  return (
    <div className={styles.shell} data-testid="customer-layout">
      <header className={styles.header}>
        <div className={styles.table} data-testid="customer-layout-table">
          {tableNumber != null ? `${tableNumber}번 테이블` : '테이블'}
        </div>
        <nav className={styles.nav} aria-label="고객 메뉴">
          <NavLink to="/customer/menu" className={tabClass} data-testid="customer-layout-tab-menu">
            메뉴
          </NavLink>
          <NavLink to="/customer/orders" className={tabClass} data-testid="customer-layout-tab-orders">
            주문 내역
          </NavLink>
        </nav>
      </header>
      <div className={styles.content}>
        <Outlet />
      </div>
    </div>
  )
}
