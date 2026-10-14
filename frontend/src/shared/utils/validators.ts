import type { MenuInput } from '../api/types'

export type FieldErrors = Record<string, string>

export interface ValidationResult<T> {
  errors: FieldErrors
  value?: T
}

const MSG = {
  storeId: '매장 식별자를 입력해주세요.',
  tableNumber: '테이블 번호는 1~999 사이 숫자로 입력해주세요.',
  tablePassword: '비밀번호는 숫자 4자리입니다.',
  required: '해당 항목을 입력해주세요.',
  menuName: '메뉴명은 1~50자로 입력해주세요.',
  price: '가격은 100원~1,000,000원 사이 정수로 입력해주세요.',
  description: '설명은 300자 이내로 입력해주세요.',
  category: '카테고리는 1~30자로 입력해주세요.',
  imageUrl: '이미지 주소는 http 또는 https URL이어야 합니다.',
  dateRange: '시작일이 종료일보다 늦을 수 없습니다.',
} as const

function parseInteger(raw: string): number | null {
  const s = raw.trim()
  if (!/^\d+$/.test(s)) return null
  return Number(s)
}

function validTableNumber(raw: string): number | null {
  const n = parseInteger(raw)
  return n !== null && n >= 1 && n <= 999 ? n : null
}

export interface TableSetupForm {
  storeId: string
  tableNumber: string
  password: string
}

export function validateTableSetup(
  form: TableSetupForm,
): ValidationResult<{ storeId: string; tableNumber: number; password: string }> {
  const errors: FieldErrors = {}
  const storeId = form.storeId.trim()
  if (storeId.length < 1 || storeId.length > 50) errors.storeId = MSG.storeId
  const tableNumber = validTableNumber(form.tableNumber)
  if (tableNumber === null) errors.tableNumber = MSG.tableNumber
  if (!/^\d{4}$/.test(form.password)) errors.password = MSG.tablePassword
  if (Object.keys(errors).length > 0 || tableNumber === null) return { errors }
  return { errors, value: { storeId, tableNumber, password: form.password } }
}

export interface AdminLoginForm {
  storeId: string
  username: string
  password: string
}

export function validateAdminLogin(form: AdminLoginForm): ValidationResult<AdminLoginForm> {
  const errors: FieldErrors = {}
  const storeId = form.storeId.trim()
  const username = form.username.trim()
  if (!storeId) errors.storeId = MSG.required
  if (!username) errors.username = MSG.required
  if (!form.password) errors.password = MSG.required
  if (Object.keys(errors).length > 0) return { errors }
  return { errors, value: { storeId, username, password: form.password } }
}

export interface TableRegisterForm {
  tableNumber: string
  password: string
}

export function validateTableRegister(
  form: TableRegisterForm,
): ValidationResult<{ tableNumber: number; password: string }> {
  const errors: FieldErrors = {}
  const tableNumber = validTableNumber(form.tableNumber)
  if (tableNumber === null) errors.tableNumber = MSG.tableNumber
  if (!/^\d{4}$/.test(form.password)) errors.password = MSG.tablePassword
  if (Object.keys(errors).length > 0 || tableNumber === null) return { errors }
  return { errors, value: { tableNumber, password: form.password } }
}

export interface MenuForm {
  name: string
  price: string
  description: string
  category: string
  imageUrl: string
}

function isHttpUrl(raw: string): boolean {
  try {
    const u = new URL(raw)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

export function validateMenuForm(form: MenuForm): ValidationResult<MenuInput> {
  const errors: FieldErrors = {}
  const name = form.name.trim()
  const description = form.description.trim()
  const category = form.category.trim()
  const imageUrl = form.imageUrl.trim()

  if (name.length < 1 || name.length > 50) errors.name = MSG.menuName
  const price = parseInteger(form.price)
  if (price === null || price < 100 || price > 1_000_000) errors.price = MSG.price
  if (description.length > 300) errors.description = MSG.description
  if (category.length < 1 || category.length > 30) errors.category = MSG.category
  if (imageUrl && !isHttpUrl(imageUrl)) errors.imageUrl = MSG.imageUrl

  if (Object.keys(errors).length > 0 || price === null) return { errors }
  return {
    errors,
    value: { name, price, description, category, imageUrl: imageUrl || null },
  }
}

/** 시작일/종료일 (YYYY-MM-DD). 비어 있으면 그 쪽은 제한 없음 */
export function validateDateRange(from: string, to: string): FieldErrors {
  if (from && to && from > to) return { to: MSG.dateRange }
  return {}
}

export const MAX_CART_QUANTITY = 20
