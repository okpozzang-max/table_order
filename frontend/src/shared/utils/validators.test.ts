import { describe, expect, it } from 'vitest'
import {
  validateAdminLogin,
  validateDateRange,
  validateMenuForm,
  validateTableRegister,
  validateTableSetup,
} from './validators'

describe('validateTableSetup', () => {
  it('올바른 입력이면 파싱된 값을 반환한다', () => {
    const r = validateTableSetup({ storeId: ' demo ', tableNumber: '3', password: '1234' })
    expect(r.errors).toEqual({})
    expect(r.value).toEqual({ storeId: 'demo', tableNumber: 3, password: '1234' })
  })

  it('필수값 누락과 형식 오류를 필드별로 알린다', () => {
    const r = validateTableSetup({ storeId: '', tableNumber: '0', password: '12a4' })
    expect(Object.keys(r.errors).sort()).toEqual(['password', 'storeId', 'tableNumber'])
    expect(r.value).toBeUndefined()
  })

  it('비밀번호는 숫자 4자리만 허용한다', () => {
    expect(validateTableSetup({ storeId: 'a', tableNumber: '1', password: '123' }).errors.password).toBeDefined()
    expect(validateTableSetup({ storeId: 'a', tableNumber: '1', password: '12345' }).errors.password).toBeDefined()
    expect(validateTableSetup({ storeId: 'a', tableNumber: '1', password: '0000' }).errors.password).toBeUndefined()
  })

  it('테이블 번호는 1~999 정수', () => {
    expect(validateTableSetup({ storeId: 'a', tableNumber: '999', password: '1234' }).errors).toEqual({})
    expect(validateTableSetup({ storeId: 'a', tableNumber: '1000', password: '1234' }).errors.tableNumber).toBeDefined()
    expect(validateTableSetup({ storeId: 'a', tableNumber: '1.5', password: '1234' }).errors.tableNumber).toBeDefined()
  })
})

describe('validateAdminLogin', () => {
  it('세 항목 모두 필수', () => {
    const r = validateAdminLogin({ storeId: '', username: ' ', password: '' })
    expect(Object.keys(r.errors).sort()).toEqual(['password', 'storeId', 'username'])
  })
  it('통과 시 공백을 제거한 값을 반환', () => {
    const r = validateAdminLogin({ storeId: ' demo', username: 'admin ', password: 'pw' })
    expect(r.value).toEqual({ storeId: 'demo', username: 'admin', password: 'pw' })
  })
})

describe('validateTableRegister', () => {
  it('번호와 4자리 비밀번호', () => {
    expect(validateTableRegister({ tableNumber: '7', password: '0007' }).value).toEqual({
      tableNumber: 7,
      password: '0007',
    })
    expect(validateTableRegister({ tableNumber: '', password: 'abcd' }).errors).toHaveProperty('tableNumber')
  })
})

describe('validateMenuForm', () => {
  const base = { name: '김치찌개', price: '9000', description: '', category: '메인', imageUrl: '' }

  it('정상 입력', () => {
    const r = validateMenuForm(base)
    expect(r.errors).toEqual({})
    expect(r.value).toEqual({ name: '김치찌개', price: 9000, description: '', category: '메인', imageUrl: null })
  })

  it('가격 범위: 100~1,000,000 정수', () => {
    expect(validateMenuForm({ ...base, price: '99' }).errors.price).toBeDefined()
    expect(validateMenuForm({ ...base, price: '100' }).errors.price).toBeUndefined()
    expect(validateMenuForm({ ...base, price: '1000000' }).errors.price).toBeUndefined()
    expect(validateMenuForm({ ...base, price: '1000001' }).errors.price).toBeDefined()
    expect(validateMenuForm({ ...base, price: '9000.5' }).errors.price).toBeDefined()
    expect(validateMenuForm({ ...base, price: '-1' }).errors.price).toBeDefined()
  })

  it('길이 제한: 메뉴명 50, 설명 300, 카테고리 30', () => {
    expect(validateMenuForm({ ...base, name: 'a'.repeat(51) }).errors.name).toBeDefined()
    expect(validateMenuForm({ ...base, name: 'a'.repeat(50) }).errors.name).toBeUndefined()
    expect(validateMenuForm({ ...base, description: 'a'.repeat(301) }).errors.description).toBeDefined()
    expect(validateMenuForm({ ...base, category: 'a'.repeat(31) }).errors.category).toBeDefined()
    expect(validateMenuForm({ ...base, name: ' ' }).errors.name).toBeDefined()
    expect(validateMenuForm({ ...base, category: '' }).errors.category).toBeDefined()
  })

  it('이미지 URL은 선택이며 http/https만 허용', () => {
    expect(validateMenuForm({ ...base, imageUrl: 'https://example.com/a.png' }).value?.imageUrl).toBe(
      'https://example.com/a.png',
    )
    expect(validateMenuForm({ ...base, imageUrl: 'ftp://example.com/a.png' }).errors.imageUrl).toBeDefined()
    expect(validateMenuForm({ ...base, imageUrl: 'not a url' }).errors.imageUrl).toBeDefined()
  })
})

describe('validateDateRange', () => {
  it('시작일이 종료일보다 늦으면 오류', () => {
    expect(validateDateRange('2026-10-10', '2026-10-01')).toHaveProperty('to')
    expect(validateDateRange('2026-10-01', '2026-10-10')).toEqual({})
    expect(validateDateRange('', '2026-10-10')).toEqual({})
    expect(validateDateRange('2026-10-10', '')).toEqual({})
  })
})
