import type { ApiErrorBody, ErrorCode, ServerErrorCode } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCode
  readonly body?: ApiErrorBody

  constructor(status: number, code: ErrorCode, body?: ApiErrorBody, message?: string) {
    super(message ?? body?.message ?? code)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }

  get fields(): Record<string, string> {
    return this.body?.fields ?? {}
  }

  get retryAfterSeconds(): number | undefined {
    return this.body?.retryAfterSeconds
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}

export function networkError(): ApiError {
  return new ApiError(0, 'NETWORK_ERROR')
}

const KNOWN_CODES: ReadonlySet<string> = new Set<ServerErrorCode>([
  'INVALID_CREDENTIALS',
  'UNAUTHORIZED',
  'ACCOUNT_LOCKED',
  'VALIDATION_ERROR',
  'NOT_FOUND',
  'MENU_UNAVAILABLE',
  'PRICE_CHANGED',
  'INVALID_TRANSITION',
  'NO_ACTIVE_SESSION',
  'DUPLICATE_TABLE',
  'INTERNAL_ERROR',
])

function fallbackCode(status: number): ServerErrorCode {
  switch (status) {
    case 401:
      return 'UNAUTHORIZED'
    case 404:
      return 'NOT_FOUND'
    case 422:
      return 'VALIDATION_ERROR'
    case 429:
      return 'ACCOUNT_LOCKED'
    default:
      return 'INTERNAL_ERROR'
  }
}

/** 실패한 fetch 응답을 ApiError로 정규화한다. 본문이 계약 형식이 아니면 상태 코드로 추정한다. */
export async function parseErrorResponse(res: Response): Promise<ApiError> {
  let body: ApiErrorBody | undefined
  try {
    const json = (await res.json()) as unknown
    if (
      json &&
      typeof json === 'object' &&
      typeof (json as { code?: unknown }).code === 'string' &&
      KNOWN_CODES.has((json as { code: string }).code)
    ) {
      body = json as ApiErrorBody
    }
  } catch {
    // 본문이 JSON이 아닌 경우: 상태 코드로 추정
  }
  return new ApiError(res.status, body?.code ?? fallbackCode(res.status), body)
}
