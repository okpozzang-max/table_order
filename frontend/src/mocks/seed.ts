import type { Menu } from '../shared/api/types'

export interface MockTable {
  id: number
  tableNumber: number
  /** 개발용 가짜 값 (평문). 실제 서버는 해시로만 저장한다 */
  password: string
  activeSessionId: string | null
}

export interface MockOrderRecord {
  id: number
  orderNumber: string
  tableId: number
  tableNumber: number
  sessionId: string
  createdAt: string
  status: 'PENDING' | 'PREPARING' | 'COMPLETED'
  totalAmount: number
  items: { menuId: number; menuName: string; quantity: number; unitPrice: number }[]
  clientOrderId: string
}

export interface MockHistoryRecord {
  orderId: number
  orderNumber: string
  tableNumber: number
  createdAt: string
  items: { menuId: number; menuName: string; quantity: number; unitPrice: number }[]
  totalAmount: number
  completedAt: string
}

export interface MockState {
  storeId: string
  adminUsername: string
  adminPassword: string
  nextMenuId: number
  nextTableId: number
  nextOrderId: number
  nextSessionSeq: number
  categoryOrder: string[]
  menus: Menu[]
  tables: MockTable[]
  orders: MockOrderRecord[]
  history: MockHistoryRecord[]
  adminFailures: number
  adminLockedUntil: number | null
}

interface SeedMenu {
  name: string
  price: number
  description: string
  category: string
}

const SEED_MENUS: SeedMenu[] = [
  { name: '김치찌개', price: 9000, description: '잘 익은 김치와 돼지고기를 넣고 끓인 찌개', category: '메인' },
  { name: '된장찌개', price: 8500, description: '구수한 된장에 두부와 채소를 넣은 찌개', category: '메인' },
  { name: '제육볶음', price: 11000, description: '매콤하게 볶은 돼지고기 볶음', category: '메인' },
  { name: '비빔밥', price: 9500, description: '나물과 고추장을 곁들인 비빔밥', category: '메인' },
  { name: '계란말이', price: 6000, description: '부드러운 계란말이', category: '사이드' },
  { name: '공기밥', price: 1000, description: '갓 지은 흰쌀밥', category: '사이드' },
  { name: '김치전', price: 8000, description: '바삭하게 부친 김치전', category: '사이드' },
  { name: '콜라', price: 2000, description: '355ml 캔', category: '음료' },
  { name: '사이다', price: 2000, description: '355ml 캔', category: '음료' },
  { name: '맥주', price: 4500, description: '500ml 생맥주', category: '음료' },
  { name: '식혜', price: 3000, description: '달콤한 전통 음료', category: '음료' },
  { name: '아이스크림', price: 3500, description: '바닐라 아이스크림', category: '디저트' },
]

export const MOCK_STORE_ID = 'demo'
export const MOCK_ADMIN_USERNAME = 'admin'
export const MOCK_ADMIN_PASSWORD = 'admin1234'
export const MOCK_TABLE_PASSWORD = '1234'

/** 개발/테스트용 초기 데이터. 매번 새 객체를 반환한다. */
export function createSeedState(): MockState {
  const categoryOrder: string[] = []
  const orderInCategory: Record<string, number> = {}
  const menus: Menu[] = SEED_MENUS.map((m, idx) => {
    if (!categoryOrder.includes(m.category)) categoryOrder.push(m.category)
    orderInCategory[m.category] = (orderInCategory[m.category] ?? 0) + 1
    return {
      id: idx + 1,
      name: m.name,
      price: m.price,
      description: m.description,
      category: m.category,
      imageUrl: null,
      displayOrder: orderInCategory[m.category],
    }
  })
  const tables: MockTable[] = [1, 2, 3, 4, 5].map((n) => ({
    id: n,
    tableNumber: n,
    password: MOCK_TABLE_PASSWORD,
    activeSessionId: null,
  }))
  return {
    storeId: MOCK_STORE_ID,
    adminUsername: MOCK_ADMIN_USERNAME,
    adminPassword: MOCK_ADMIN_PASSWORD,
    nextMenuId: menus.length + 1,
    nextTableId: tables.length + 1,
    nextOrderId: 1,
    nextSessionSeq: 1,
    categoryOrder,
    menus,
    tables,
    orders: [],
    history: [],
    adminFailures: 0,
    adminLockedUntil: null,
  }
}
