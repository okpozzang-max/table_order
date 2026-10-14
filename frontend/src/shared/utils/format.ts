import type { OrderItem } from '../api/types'

export function formatKRW(amount: number): string {
  return `${amount.toLocaleString('ko-KR')}원`
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** ISO 문자열 -> `YYYY-MM-DD HH:mm` (브라우저 로컬 시간) */
export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 첫 메뉴명 + `외 N건` (항목이 1개면 메뉴명만) */
export function summarizeItems(items: Pick<OrderItem, 'menuName'>[]): string {
  if (items.length === 0) return ''
  if (items.length === 1) return items[0].menuName
  return `${items[0].menuName} 외 ${items.length - 1}건`
}

/** 장바구니 내용 식별용 서명 (menuId:quantity 정렬 결합) */
export function cartSignature(items: { menuId: number; quantity: number }[]): string {
  return [...items]
    .sort((a, b) => a.menuId - b.menuId)
    .map((i) => `${i.menuId}:${i.quantity}`)
    .join(',')
}

/** 남은 초 -> `M분 SS초` */
export function formatRemaining(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds))
  const m = Math.floor(s / 60)
  const r = s % 60
  return m > 0 ? `${m}분 ${pad(r)}초` : `${r}초`
}
