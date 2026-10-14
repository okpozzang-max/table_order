import { ApiError } from '../shared/api/errors'
import type {
  AdminLoginRequest,
  CategoryMenus,
  HistoryOrder,
  Menu,
  MenuInput,
  Order,
  OrderCreateRequest,
  OrderPage,
  OrderStatus,
  ServerEvent,
  SessionSummary,
  TableInfo,
  TableLoginRequest,
  TableRegisterRequest,
  TableSummary,
  TableTokenResponse,
  TokenResponse,
} from '../shared/api/types'
import { NEXT_ORDER_STATUS } from '../shared/api/types'
import { createSeedState } from './seed'
import type { MockOrderRecord, MockState, MockTable } from './seed'

const TOKEN_TTL_MS = 16 * 60 * 60 * 1000
const LOCK_SECONDS = 15 * 60
const MAX_FAILURES = 5
const DASHBOARD_PREVIEW = 3

export interface MockBackendOptions {
  /** 지정하면 localStorage에 상태를 저장하고 매 작업 전에 다시 읽는다 (탭 간 공유) */
  storageKey?: string
  /** 지정하면 BroadcastChannel로 이벤트를 다른 탭에 전달한다 */
  channelName?: string
  now?: () => number
  initialState?: MockState
}

function validation(fields: Record<string, string>): ApiError {
  return new ApiError(422, 'VALIDATION_ERROR', { code: 'VALIDATION_ERROR', fields })
}

function conflict(code: 'MENU_UNAVAILABLE' | 'PRICE_CHANGED' | 'INVALID_TRANSITION' | 'NO_ACTIVE_SESSION' | 'DUPLICATE_TABLE', details?: { menuIds?: number[]; currentPrices?: { menuId: number; price: number }[] }): ApiError {
  return new ApiError(409, code, { code, details })
}

function notFound(): ApiError {
  return new ApiError(404, 'NOT_FOUND', { code: 'NOT_FOUND' })
}

function unauthorized(): ApiError {
  return new ApiError(401, 'UNAUTHORIZED', { code: 'UNAUTHORIZED' })
}

function toOrder(r: MockOrderRecord): Order {
  return {
    id: r.id,
    orderNumber: r.orderNumber,
    tableId: r.tableId,
    tableNumber: r.tableNumber,
    sessionId: r.sessionId,
    createdAt: r.createdAt,
    status: r.status,
    totalAmount: r.totalAmount,
    items: r.items.map((i) => ({ ...i })),
  }
}

/**
 * 계약(contracts/openapi.yaml)의 서버 동작을 메모리에서 흉내 내는 가짜 백엔드.
 * 서버 규칙(가격 재계산, 멱등, 세션, 순차 전이, 잠금, 검증)을 동일하게 재현한다.
 */
export class MockBackend {
  private state: MockState
  private readonly listeners = new Set<(e: ServerEvent) => void>()
  private channel: BroadcastChannel | null = null
  private readonly opts: MockBackendOptions

  constructor(opts: MockBackendOptions = {}) {
    this.opts = opts
    this.state = opts.initialState ?? createSeedState()
    if (opts.storageKey) {
      const raw = localStorage.getItem(opts.storageKey)
      if (raw) this.state = JSON.parse(raw) as MockState
      else this.save()
    }
    if (opts.channelName && typeof BroadcastChannel !== 'undefined') {
      this.channel = new BroadcastChannel(opts.channelName)
      this.channel.onmessage = (m: MessageEvent<ServerEvent>) => {
        this.listeners.forEach((fn) => fn(m.data))
      }
    }
  }

  // ---------- 인프라 ----------

  now(): number {
    return this.opts.now ? this.opts.now() : Date.now()
  }

  subscribe(fn: (e: ServerEvent) => void): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  private emit(event: ServerEvent): void {
    this.listeners.forEach((fn) => fn(event))
    this.channel?.postMessage(event)
  }

  private load(): void {
    const key = this.opts.storageKey
    if (!key) return
    const raw = localStorage.getItem(key)
    if (raw) this.state = JSON.parse(raw) as MockState
  }

  private save(): void {
    const key = this.opts.storageKey
    if (key) localStorage.setItem(key, JSON.stringify(this.state))
  }

  /** 읽기 전용 작업 */
  private read<T>(fn: () => T): T {
    this.load()
    return structuredClone(fn())
  }

  /** 상태를 바꾸는 작업. 성공 시 저장하고, 이벤트는 저장 후 발행한다 (커밋 후 발행) */
  private write<T>(fn: (events: ServerEvent[]) => T): T {
    this.load()
    const events: ServerEvent[] = []
    const result = fn(events)
    this.save()
    events.forEach((e) => this.emit(e))
    return structuredClone(result)
  }

  private issueToken(prefix: string): { token: string; expiresAt: string } {
    const exp = this.now() + TOKEN_TTL_MS
    return { token: `${prefix}.${exp}`, expiresAt: new Date(exp).toISOString() }
  }

  private parseToken(token: string | null, kind: 'table' | 'admin'): { tableId?: number } {
    if (!token) throw unauthorized()
    const parts = token.split('.')
    const exp = Number(parts[parts.length - 1])
    if (!Number.isFinite(exp) || exp <= this.now()) throw unauthorized()
    if (kind === 'admin') {
      if (parts[0] !== 'mock-admin' || parts.length !== 2) throw unauthorized()
      return {}
    }
    if (parts[0] !== 'mock-table' || parts.length !== 3) throw unauthorized()
    return { tableId: Number(parts[1]) }
  }

  private requireAdmin(token: string | null): void {
    this.parseToken(token, 'admin')
  }

  private requireTable(token: string | null): MockTable {
    const { tableId } = this.parseToken(token, 'table')
    const table = this.state.tables.find((t) => t.id === tableId)
    if (!table) throw unauthorized()
    return table
  }

  // ---------- 고객 ----------

  customerLogin(req: TableLoginRequest): TableTokenResponse {
    return this.read(() => {
      const fields: Record<string, string> = {}
      if (!req.storeId?.trim()) fields.storeId = '매장 식별자를 입력해주세요.'
      if (!Number.isInteger(req.tableNumber) || req.tableNumber < 1 || req.tableNumber > 999) {
        fields.tableNumber = '테이블 번호는 1~999 사이 숫자로 입력해주세요.'
      }
      if (!/^\d{4}$/.test(req.password ?? '')) fields.password = '비밀번호는 숫자 4자리입니다.'
      if (Object.keys(fields).length > 0) throw validation(fields)

      const table = this.state.tables.find((t) => t.tableNumber === req.tableNumber)
      if (req.storeId.trim() !== this.state.storeId || !table || table.password !== req.password) {
        throw new ApiError(401, 'INVALID_CREDENTIALS', { code: 'INVALID_CREDENTIALS' })
      }
      const { token, expiresAt } = this.issueToken(`mock-table.${table.id}`)
      return { accessToken: token, expiresAt, tableId: table.id, tableNumber: table.tableNumber }
    })
  }

  getCustomerMenus(token: string | null): CategoryMenus[] {
    return this.read(() => {
      this.requireTable(token)
      return this.groupedMenus()
    })
  }

  createOrder(token: string | null, req: OrderCreateRequest): Order {
    return this.write((events) => {
      const table = this.requireTable(token)

      const existing = this.state.orders.find(
        (o) => o.clientOrderId === req.clientOrderId && o.tableId === table.id,
      )
      if (existing) return toOrder(existing)

      if (!req.items || req.items.length === 0) throw validation({ items: '주문할 메뉴를 선택해주세요.' })
      for (const it of req.items) {
        if (!Number.isInteger(it.quantity) || it.quantity < 1 || it.quantity > 20) {
          throw validation({ items: '메뉴 수량은 1~20개입니다.' })
        }
      }

      const missing = req.items.filter((it) => !this.state.menus.some((m) => m.id === it.menuId))
      if (missing.length > 0) throw conflict('MENU_UNAVAILABLE', { menuIds: missing.map((m) => m.menuId) })

      const lines = req.items.map((it) => {
        const menu = this.state.menus.find((m) => m.id === it.menuId) as Menu
        return { menuId: menu.id, menuName: menu.name, quantity: it.quantity, unitPrice: menu.price }
      })
      const total = lines.reduce((sum, l) => sum + l.unitPrice * l.quantity, 0)
      if (total !== req.clientTotal) {
        throw conflict('PRICE_CHANGED', {
          currentPrices: lines.map((l) => ({ menuId: l.menuId, price: l.unitPrice })),
        })
      }

      if (!table.activeSessionId) {
        table.activeSessionId = `S-${table.tableNumber}-${this.state.nextSessionSeq++}`
      }
      const id = this.state.nextOrderId++
      const record: MockOrderRecord = {
        id,
        orderNumber: String(id).padStart(4, '0'),
        tableId: table.id,
        tableNumber: table.tableNumber,
        sessionId: table.activeSessionId,
        createdAt: new Date(this.now()).toISOString(),
        status: 'PENDING',
        totalAmount: total,
        items: lines,
        clientOrderId: req.clientOrderId,
      }
      this.state.orders.push(record)
      events.push({ type: 'order_created', tableId: table.id, payload: { orderId: id } })
      return toOrder(record)
    })
  }

  listSessionOrders(token: string | null, page: number, size: number): OrderPage {
    return this.read(() => {
      const table = this.requireTable(token)
      const mine = this.state.orders
        .filter((o) => o.tableId === table.id && o.sessionId === table.activeSessionId)
        .sort((a, b) => b.id - a.id)
      const start = page * size
      const slice = mine.slice(start, start + size)
      return { items: slice.map(toOrder), page, size, hasNext: start + size < mine.length }
    })
  }

  // ---------- 관리자 인증 ----------

  adminLogin(req: AdminLoginRequest): TokenResponse {
    return this.write(() => {
      const fields: Record<string, string> = {}
      if (!req.storeId?.trim()) fields.storeId = '해당 항목을 입력해주세요.'
      if (!req.username?.trim()) fields.username = '해당 항목을 입력해주세요.'
      if (!req.password) fields.password = '해당 항목을 입력해주세요.'
      if (Object.keys(fields).length > 0) throw validation(fields)

      const now = this.now()
      const lockedUntil = this.state.adminLockedUntil
      if (lockedUntil && lockedUntil > now) {
        throw this.locked(Math.ceil((lockedUntil - now) / 1000))
      }
      if (lockedUntil && lockedUntil <= now) {
        this.state.adminLockedUntil = null
        this.state.adminFailures = 0
      }

      const ok =
        req.storeId.trim() === this.state.storeId &&
        req.username.trim() === this.state.adminUsername &&
        req.password === this.state.adminPassword
      if (!ok) {
        this.state.adminFailures += 1
        if (this.state.adminFailures >= MAX_FAILURES) {
          this.state.adminLockedUntil = now + LOCK_SECONDS * 1000
          this.state.adminFailures = 0
          // 상태를 저장하기 위해 오류를 던지기 전에 write 래퍼가 save하도록 결과로 반환할 수 없으므로 직접 저장
          this.save()
          throw this.locked(LOCK_SECONDS)
        }
        this.save()
        throw new ApiError(401, 'INVALID_CREDENTIALS', { code: 'INVALID_CREDENTIALS' })
      }
      this.state.adminFailures = 0
      this.state.adminLockedUntil = null
      const { token, expiresAt } = this.issueToken('mock-admin')
      return { accessToken: token, expiresAt }
    })
  }

  private locked(seconds: number): ApiError {
    return new ApiError(429, 'ACCOUNT_LOCKED', { code: 'ACCOUNT_LOCKED', retryAfterSeconds: seconds })
  }

  // ---------- 관리자 주문/대시보드 ----------

  getDashboard(token: string | null, table?: number | null): TableSummary[] {
    return this.read(() => {
      this.requireAdmin(token)
      const tables = [...this.state.tables].sort((a, b) => a.tableNumber - b.tableNumber)
      if (table != null && !tables.some((t) => t.tableNumber === table)) throw notFound()
      return tables
        .filter((t) => table == null || t.tableNumber === table)
        .map((t) => this.summary(t, table != null))
    })
  }

  getOrder(token: string | null, orderId: number): Order {
    return this.read(() => {
      this.requireAdmin(token)
      const o = this.state.orders.find((x) => x.id === orderId)
      if (!o) throw notFound()
      return toOrder(o)
    })
  }

  changeOrderStatus(token: string | null, orderId: number, status: OrderStatus): Order {
    return this.write((events) => {
      this.requireAdmin(token)
      if (!['PENDING', 'PREPARING', 'COMPLETED'].includes(status)) {
        throw validation({ status: '올바르지 않은 상태입니다.' })
      }
      const o = this.state.orders.find((x) => x.id === orderId)
      if (!o) throw notFound()
      if (NEXT_ORDER_STATUS[o.status] !== status) throw conflict('INVALID_TRANSITION')
      o.status = status
      events.push({ type: 'order_status_changed', tableId: o.tableId, payload: { orderId: o.id, status } })
      return toOrder(o)
    })
  }

  deleteOrder(token: string | null, orderId: number): TableSummary {
    return this.write((events) => {
      this.requireAdmin(token)
      const idx = this.state.orders.findIndex((x) => x.id === orderId)
      if (idx === -1) throw notFound()
      const [removed] = this.state.orders.splice(idx, 1)
      const table = this.state.tables.find((t) => t.id === removed.tableId) as MockTable
      events.push({ type: 'order_deleted', tableId: table.id, payload: { orderId } })
      return this.summary(table, false)
    })
  }

  streamAdminEvents(token: string | null, onEvent: (e: ServerEvent) => void, signal: AbortSignal): Promise<void> {
    this.requireAdmin(token)
    return new Promise<void>((resolve) => {
      if (signal.aborted) return resolve()
      const unsubscribe = this.subscribe(onEvent)
      signal.addEventListener(
        'abort',
        () => {
          unsubscribe()
          resolve()
        },
        { once: true },
      )
    })
  }

  // ---------- 관리자 테이블 ----------

  listTables(token: string | null): TableInfo[] {
    return this.read(() => {
      this.requireAdmin(token)
      return [...this.state.tables]
        .sort((a, b) => a.tableNumber - b.tableNumber)
        .map((t) => ({ id: t.id, tableNumber: t.tableNumber, sessionActive: t.activeSessionId !== null }))
    })
  }

  registerTable(token: string | null, req: TableRegisterRequest): TableInfo {
    return this.write(() => {
      this.requireAdmin(token)
      const fields: Record<string, string> = {}
      if (!Number.isInteger(req.tableNumber) || req.tableNumber < 1 || req.tableNumber > 999) {
        fields.tableNumber = '테이블 번호는 1~999 사이 숫자로 입력해주세요.'
      }
      if (!/^\d{4}$/.test(req.password ?? '')) fields.password = '비밀번호는 숫자 4자리입니다.'
      if (Object.keys(fields).length > 0) throw validation(fields)
      if (this.state.tables.some((t) => t.tableNumber === req.tableNumber)) throw conflict('DUPLICATE_TABLE')
      const table: MockTable = {
        id: this.state.nextTableId++,
        tableNumber: req.tableNumber,
        password: req.password,
        activeSessionId: null,
      }
      this.state.tables.push(table)
      return { id: table.id, tableNumber: table.tableNumber, sessionActive: false }
    })
  }

  endSession(token: string | null, tableId: number): SessionSummary {
    return this.write((events) => {
      this.requireAdmin(token)
      const table = this.state.tables.find((t) => t.id === tableId)
      if (!table) throw notFound()
      if (!table.activeSessionId) throw conflict('NO_ACTIVE_SESSION')
      const endedAt = new Date(this.now()).toISOString()
      const sessionOrders = this.state.orders.filter(
        (o) => o.tableId === table.id && o.sessionId === table.activeSessionId,
      )
      for (const o of sessionOrders) {
        this.state.history.push({
          orderId: o.id,
          orderNumber: o.orderNumber,
          tableNumber: o.tableNumber,
          createdAt: o.createdAt,
          items: o.items.map((i) => ({ ...i })),
          totalAmount: o.totalAmount,
          completedAt: endedAt,
        })
      }
      this.state.orders = this.state.orders.filter((o) => !sessionOrders.includes(o))
      table.activeSessionId = null
      events.push({ type: 'session_ended', tableId: table.id, payload: {} })
      return {
        tableId: table.id,
        endedAt,
        archivedOrderCount: sessionOrders.length,
        archivedTotalAmount: sessionOrders.reduce((s, o) => s + o.totalAmount, 0),
      }
    })
  }

  getTableHistory(token: string | null, tableId: number, range?: { from?: string; to?: string }): HistoryOrder[] {
    return this.read(() => {
      this.requireAdmin(token)
      const table = this.state.tables.find((t) => t.id === tableId)
      if (!table) throw notFound()
      if (range?.from && range?.to && range.from > range.to) {
        throw validation({ to: '시작일이 종료일보다 늦을 수 없습니다.' })
      }
      return this.state.history
        .filter((h) => h.tableNumber === table.tableNumber)
        .filter((h) => {
          const day = localDay(h.createdAt)
          return (!range?.from || day >= range.from) && (!range?.to || day <= range.to)
        })
        .sort((a, b) => (a.completedAt === b.completedAt ? b.orderId - a.orderId : a.completedAt < b.completedAt ? 1 : -1))
    })
  }

  // ---------- 관리자 메뉴 ----------

  listAdminMenus(token: string | null): CategoryMenus[] {
    return this.read(() => {
      this.requireAdmin(token)
      return this.groupedMenus()
    })
  }

  createMenu(token: string | null, input: MenuInput): Menu {
    return this.write((events) => {
      this.requireAdmin(token)
      this.validateMenu(input)
      const category = input.category.trim()
      if (!this.state.categoryOrder.includes(category)) this.state.categoryOrder.push(category)
      const maxOrder = Math.max(0, ...this.state.menus.filter((m) => m.category === category).map((m) => m.displayOrder))
      const menu: Menu = {
        id: this.state.nextMenuId++,
        name: input.name.trim(),
        price: input.price,
        description: input.description.trim(),
        category,
        imageUrl: input.imageUrl?.trim() || null,
        displayOrder: maxOrder + 1,
      }
      this.state.menus.push(menu)
      events.push({ type: 'menu_changed', tableId: null, payload: {} })
      return menu
    })
  }

  updateMenu(token: string | null, menuId: number, input: MenuInput): Menu {
    return this.write((events) => {
      this.requireAdmin(token)
      const menu = this.state.menus.find((m) => m.id === menuId)
      if (!menu) throw notFound()
      this.validateMenu(input)
      const category = input.category.trim()
      if (category !== menu.category) {
        if (!this.state.categoryOrder.includes(category)) this.state.categoryOrder.push(category)
        const maxOrder = Math.max(0, ...this.state.menus.filter((m) => m.category === category).map((m) => m.displayOrder))
        menu.displayOrder = maxOrder + 1
        menu.category = category
      }
      menu.name = input.name.trim()
      menu.price = input.price
      menu.description = input.description.trim()
      menu.imageUrl = input.imageUrl?.trim() || null
      this.pruneEmptyCategories()
      events.push({ type: 'menu_changed', tableId: null, payload: {} })
      return menu
    })
  }

  deleteMenu(token: string | null, menuId: number): void {
    this.write((events) => {
      this.requireAdmin(token)
      const idx = this.state.menus.findIndex((m) => m.id === menuId)
      if (idx === -1) throw notFound()
      this.state.menus.splice(idx, 1)
      this.pruneEmptyCategories()
      events.push({ type: 'menu_changed', tableId: null, payload: {} })
    })
  }

  reorderMenus(token: string | null, category: string, orderedIds: number[]): void {
    this.write((events) => {
      this.requireAdmin(token)
      const inCategory = this.state.menus.filter((m) => m.category === category)
      const sameSet =
        inCategory.length === orderedIds.length &&
        inCategory.every((m) => orderedIds.includes(m.id)) &&
        new Set(orderedIds).size === orderedIds.length
      if (inCategory.length === 0) throw notFound()
      if (!sameSet) throw validation({ orderedIds: '해당 카테고리의 모든 메뉴 ID가 필요해요.' })
      orderedIds.forEach((id, idx) => {
        const m = this.state.menus.find((x) => x.id === id) as Menu
        m.displayOrder = idx + 1
      })
      events.push({ type: 'menu_changed', tableId: null, payload: {} })
    })
  }

  // ---------- 내부 도우미 ----------

  private groupedMenus(): CategoryMenus[] {
    return this.state.categoryOrder
      .map((category) => ({
        category,
        menus: this.state.menus
          .filter((m) => m.category === category)
          .sort((a, b) => a.displayOrder - b.displayOrder),
      }))
      .filter((g) => g.menus.length > 0)
  }

  private pruneEmptyCategories(): void {
    this.state.categoryOrder = this.state.categoryOrder.filter((c) => this.state.menus.some((m) => m.category === c))
  }

  private summary(table: MockTable, all: boolean): TableSummary {
    const orders = this.state.orders
      .filter((o) => o.tableId === table.id && o.sessionId === table.activeSessionId)
      .sort((a, b) => b.id - a.id)
    return {
      tableId: table.id,
      tableNumber: table.tableNumber,
      sessionActive: table.activeSessionId !== null,
      totalAmount: orders.reduce((s, o) => s + o.totalAmount, 0),
      orderCount: orders.length,
      orders: (all ? orders : orders.slice(0, DASHBOARD_PREVIEW)).map(toOrder),
    }
  }

  private validateMenu(input: MenuInput): void {
    const fields: Record<string, string> = {}
    const name = input.name?.trim() ?? ''
    if (name.length < 1 || name.length > 50) fields.name = '메뉴명은 1~50자로 입력해주세요.'
    if (!Number.isInteger(input.price) || input.price < 100 || input.price > 1_000_000) {
      fields.price = '가격은 100원~1,000,000원 사이 정수로 입력해주세요.'
    }
    if ((input.description ?? '').trim().length > 300) fields.description = '설명은 300자 이내로 입력해주세요.'
    const category = input.category?.trim() ?? ''
    if (category.length < 1 || category.length > 30) fields.category = '카테고리는 1~30자로 입력해주세요.'
    const url = input.imageUrl?.trim()
    if (url) {
      let ok = false
      try {
        const u = new URL(url)
        ok = u.protocol === 'http:' || u.protocol === 'https:'
      } catch {
        ok = false
      }
      if (!ok) fields.imageUrl = '이미지 주소는 http 또는 https URL이어야 합니다.'
    }
    if (Object.keys(fields).length > 0) throw validation(fields)
  }
}

/** ISO 시각 -> 로컬 날짜(YYYY-MM-DD) */
function localDay(iso: string): string {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
