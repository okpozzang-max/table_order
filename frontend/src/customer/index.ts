// 고객 모듈 공개 API — 앱 셸이 이 이름들에 의존한다.

// 인증
export {
  TableAuthProvider,
  useTableAuth,
  TableAuthLoadingScreen,
  TableAuthErrorScreen,
} from './auth/TableAuthProvider'
export type { TableAuthStatus, TableAuthValue } from './auth/TableAuthProvider'
export {
  TABLE_CREDENTIALS_KEY,
  readTableCredentials,
  writeTableCredentials,
  clearTableCredentials,
} from './auth/storage'
export type { TableCredentials } from './auth/storage'

// 장바구니
export { CartProvider, useCart } from './cart/CartProvider'
export type { CartValue } from './cart/CartProvider'
export type { CartItem } from './cart/cartReducer'

// 레이아웃
export { CustomerLayout } from './CustomerLayout'

// 페이지
export { TableSetupPage } from './pages/TableSetupPage'
export { MenuPage } from './pages/MenuPage'
export { OrderHistoryPage } from './pages/OrderHistoryPage'
export { OrderCompletePage } from './pages/OrderCompletePage'

// 훅 (셸/테스트에서 유용)
export { useMenus, MENUS_QUERY_KEY } from './hooks/useMenus'
export { useCreateOrder } from './hooks/useCreateOrder'
export { useSessionOrders, SESSION_ORDERS_QUERY_KEY } from './hooks/useSessionOrders'
