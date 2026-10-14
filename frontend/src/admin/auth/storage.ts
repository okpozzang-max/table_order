export const ADMIN_AUTH_STORAGE_KEY = 'tableorder.admin.auth'

export interface AdminAuthRecord {
  accessToken: string
  /** ISO date-time 문자열 */
  expiresAt: string
}

/** localStorage에서 저장된 관리자 인증 정보를 읽는다. 손상되었으면 null. */
export function readAdminAuth(): AdminAuthRecord | null {
  try {
    const raw = localStorage.getItem(ADMIN_AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof (parsed as { accessToken?: unknown }).accessToken === 'string' &&
      typeof (parsed as { expiresAt?: unknown }).expiresAt === 'string'
    ) {
      return parsed as AdminAuthRecord
    }
    return null
  } catch {
    return null
  }
}

export function writeAdminAuth(record: AdminAuthRecord): void {
  localStorage.setItem(ADMIN_AUTH_STORAGE_KEY, JSON.stringify(record))
}

export function clearAdminAuth(): void {
  localStorage.removeItem(ADMIN_AUTH_STORAGE_KEY)
}

/** expiresAt(ISO)이 now(ms) 기준 미래이면 true */
export function isFuture(expiresAt: string, now: number): boolean {
  const t = new Date(expiresAt).getTime()
  return Number.isFinite(t) && t > now
}
