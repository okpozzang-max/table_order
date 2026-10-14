import { afterEach, describe, expect, it, vi } from 'vitest'
import { configureAuthBridge, resetAuthBridge } from './authBridge'
import { ApiError, parseErrorResponse } from './errors'
import { createRealClient } from './realClient'

function jsonResponse(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  resetAuthBridge()
  vi.unstubAllGlobals()
})

describe('parseErrorResponse', () => {
  it('계약 형식의 본문을 그대로 사용한다', async () => {
    const err = await parseErrorResponse(
      jsonResponse(429, { code: 'ACCOUNT_LOCKED', retryAfterSeconds: 900 }),
    )
    expect(err.code).toBe('ACCOUNT_LOCKED')
    expect(err.status).toBe(429)
    expect(err.retryAfterSeconds).toBe(900)
  })

  it('본문이 없거나 알 수 없는 코드면 상태 코드로 추정한다', async () => {
    expect((await parseErrorResponse(jsonResponse(404))).code).toBe('NOT_FOUND')
    expect((await parseErrorResponse(jsonResponse(401, { code: 'WHATEVER' }))).code).toBe('UNAUTHORIZED')
    expect((await parseErrorResponse(jsonResponse(500, 'oops'))).code).toBe('INTERNAL_ERROR')
  })
})

describe('realClient', () => {
  it('Authorization 헤더와 쿼리 파라미터를 붙인다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { items: [], page: 0, size: 10, hasNext: false }))
    vi.stubGlobal('fetch', fetchMock)
    configureAuthBridge({ getTableToken: () => 'tok-1' })

    const client = createRealClient()
    await client.listSessionOrders(2, 10)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/customer/orders?page=2&size=10')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-1')
    expect(init.method).toBe('GET')
  })

  it('로그인 요청은 토큰 없이 JSON 본문을 보낸다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { accessToken: 'a', expiresAt: 'x' }))
    vi.stubGlobal('fetch', fetchMock)
    const client = createRealClient()
    await client.adminLogin({ storeId: 'demo', username: 'admin', password: 'pw' })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined()
    expect(JSON.parse(init.body as string)).toEqual({ storeId: 'demo', username: 'admin', password: 'pw' })
  })

  it('네트워크 실패는 NETWORK_ERROR로 정규화한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')))
    await expect(createRealClient().getCustomerMenus()).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })

  it('204 응답은 undefined를 반환한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    configureAuthBridge({ getAdminToken: () => 't' })
    await expect(createRealClient().deleteMenu(1)).resolves.toBeUndefined()
  })

  it('테이블 토큰 UNAUTHORIZED이면 재로그인 후 1회 재시도한다', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { code: 'UNAUTHORIZED' }))
      .mockResolvedValueOnce(jsonResponse(200, []))
    vi.stubGlobal('fetch', fetchMock)
    let token = 'old'
    const relogin = vi.fn(async () => {
      token = 'new'
      return true
    })
    configureAuthBridge({ getTableToken: () => token, handleTableUnauthorized: relogin })

    await expect(createRealClient().getCustomerMenus()).resolves.toEqual([])
    expect(relogin).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const second = fetchMock.mock.calls[1] as [string, RequestInit]
    expect((second[1].headers as Record<string, string>).Authorization).toBe('Bearer new')
  })

  it('재로그인에 실패하면 원래 오류를 전달한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(401, { code: 'UNAUTHORIZED' })))
    configureAuthBridge({ getTableToken: () => 't', handleTableUnauthorized: async () => false })
    await expect(createRealClient().getCustomerMenus()).rejects.toBeInstanceOf(ApiError)
  })

  it('관리자 UNAUTHORIZED는 로그아웃 핸들러를 호출한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(401, { code: 'UNAUTHORIZED' })))
    const onAdmin = vi.fn()
    configureAuthBridge({ getAdminToken: () => 't', handleAdminUnauthorized: onAdmin })
    await expect(createRealClient().listTables()).rejects.toMatchObject({ code: 'UNAUTHORIZED' })
    expect(onAdmin).toHaveBeenCalledTimes(1)
  })

  it('로그인 실패(INVALID_CREDENTIALS)는 인증 핸들러를 호출하지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(401, { code: 'INVALID_CREDENTIALS' })))
    const onAdmin = vi.fn()
    configureAuthBridge({ handleAdminUnauthorized: onAdmin })
    await expect(
      createRealClient().adminLogin({ storeId: 's', username: 'u', password: 'p' }),
    ).rejects.toMatchObject({ code: 'INVALID_CREDENTIALS' })
    expect(onAdmin).not.toHaveBeenCalled()
  })
})
