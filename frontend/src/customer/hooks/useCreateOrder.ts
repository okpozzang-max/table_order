import { useMutation } from '@tanstack/react-query'
import type { UseMutationResult } from '@tanstack/react-query'
import { useApiClient } from '../../shared/api/client'
import type { Order, OrderCreateRequest } from '../../shared/api/types'

export function useCreateOrder(): UseMutationResult<Order, unknown, OrderCreateRequest> {
  const client = useApiClient()
  return useMutation({
    mutationFn: (req: OrderCreateRequest) => client.createOrder(req),
  })
}
