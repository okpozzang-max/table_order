import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '../shared/api/errors'

/**
 * 조회 쿼리: 네트워크/서버 오류만 최대 2회 재시도(지수 백오프). 4xx(검증, 인증, 충돌)는 재시도하지 않는다.
 * 변경(mutation): 자동 재시도 없음 (주문 생성은 사용자 재시도 + 같은 clientOrderId).
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) => {
          const retryable =
            error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.code === 'INTERNAL_ERROR')
          return retryable && failureCount < 2
        },
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
      },
      mutations: { retry: false },
    },
  })
}
