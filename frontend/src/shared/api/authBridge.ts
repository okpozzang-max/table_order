import { ApiError } from './errors'

/**
 * 인증 정보 공급과 UNAUTHORIZED 처리를 앱의 인증 Provider와 ApiClient 사이에서 중개한다.
 * Provider가 마운트될 때 핸들러를 등록한다. (mock/real 클라이언트가 같은 규칙을 공유)
 */
export interface AuthBridge {
  getTableToken(): string | null
  getAdminToken(): string | null
  /** 저장된 자격 증명으로 재로그인을 시도한다. 성공하면 true (원래 요청을 1회 재시도) */
  handleTableUnauthorized(): Promise<boolean>
  /** 관리자 토큰 삭제 + 로그인 화면 이동 등 */
  handleAdminUnauthorized(): void
}

export const authBridge: AuthBridge = {
  getTableToken: () => null,
  getAdminToken: () => null,
  handleTableUnauthorized: async () => false,
  handleAdminUnauthorized: () => {},
}

export function configureAuthBridge(partial: Partial<AuthBridge>): void {
  Object.assign(authBridge, partial)
}

export function resetAuthBridge(): void {
  configureAuthBridge({
    getTableToken: () => null,
    getAdminToken: () => null,
    handleTableUnauthorized: async () => false,
    handleAdminUnauthorized: () => {},
  })
}

export type AuthKind = 'table' | 'admin' | 'none'

/**
 * 토큰을 붙여 호출하고, UNAUTHORIZED이면
 * - table: 재로그인 후 1회 재시도
 * - admin: 로그아웃 핸들러 호출 후 오류 전달
 */
export async function callWithAuth<T>(
  kind: AuthKind,
  fn: (token: string | null) => Promise<T>,
): Promise<T> {
  const tokenOf = () =>
    kind === 'table' ? authBridge.getTableToken() : kind === 'admin' ? authBridge.getAdminToken() : null
  try {
    return await fn(tokenOf())
  } catch (e) {
    if (kind !== 'none' && e instanceof ApiError && e.code === 'UNAUTHORIZED') {
      if (kind === 'table') {
        const ok = await authBridge.handleTableUnauthorized()
        if (ok) return await fn(tokenOf())
      } else {
        authBridge.handleAdminUnauthorized()
      }
    }
    throw e
  }
}
