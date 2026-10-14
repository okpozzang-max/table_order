import { useQuery } from '@tanstack/react-query'
import type { UseQueryResult } from '@tanstack/react-query'
import { useApiClient } from '../../shared/api/client'
import type { CategoryMenus } from '../../shared/api/types'

export const MENUS_QUERY_KEY = ['menus'] as const

export function useMenus(): UseQueryResult<CategoryMenus[], unknown> {
  const client = useApiClient()
  return useQuery({
    queryKey: MENUS_QUERY_KEY,
    queryFn: () => client.getCustomerMenus(),
    refetchOnWindowFocus: true,
  })
}
