import { useInfiniteQuery } from '@tanstack/react-query'
import type { UseInfiniteQueryResult, InfiniteData } from '@tanstack/react-query'
import { useApiClient } from '../../shared/api/client'
import type { OrderPage } from '../../shared/api/types'

export const SESSION_ORDERS_QUERY_KEY = ['customer', 'orders'] as const
export const SESSION_ORDERS_PAGE_SIZE = 10

export function useSessionOrders(): UseInfiniteQueryResult<InfiniteData<OrderPage>, unknown> {
  const client = useApiClient()
  return useInfiniteQuery({
    queryKey: SESSION_ORDERS_QUERY_KEY,
    queryFn: ({ pageParam }) => client.listSessionOrders(pageParam, SESSION_ORDERS_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.hasNext ? lastPage.page + 1 : undefined),
    // 탭이 보일 때만 5초마다 폴링한다 (백그라운드 중지).
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
}
