import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'
import { useApiClient } from '../../shared/api/client'
import type {
  HistoryOrder,
  Menu,
  MenuInput,
  Order,
  OrderStatus,
  SessionSummary,
  TableInfo,
  TableSummary,
  CategoryMenus,
} from '../../shared/api/types'

// ---------- Query keys ----------
export const adminKeys = {
  all: ['admin'] as const,
  dashboard: (tableFilter: number | null | undefined) =>
    ['admin', 'dashboard', tableFilter ?? 'all'] as const,
  order: (id: number) => ['admin', 'order', id] as const,
  tables: () => ['admin', 'tables'] as const,
  history: (tableId: number, from?: string, to?: string) =>
    ['admin', 'history', tableId, from ?? '', to ?? ''] as const,
  menus: () => ['admin', 'menus'] as const,
}

// ---------- Dashboard / orders ----------

export function useDashboard(tableFilter: number | null): UseQueryResult<TableSummary[]> {
  const client = useApiClient()
  return useQuery({
    queryKey: adminKeys.dashboard(tableFilter),
    queryFn: () => client.getDashboard(tableFilter ?? undefined),
  })
}

export function useOrderDetail(orderId: number | null): UseQueryResult<Order> {
  const client = useApiClient()
  return useQuery({
    queryKey: adminKeys.order(orderId ?? -1),
    queryFn: () => client.getOrder(orderId as number),
    enabled: orderId != null,
  })
}

export function useChangeOrderStatus(): UseMutationResult<
  Order,
  unknown,
  { orderId: number; status: OrderStatus }
> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, status }) => client.changeOrderStatus(orderId, status),
    retry: false,
    onSuccess: (order) => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
      queryClient.setQueryData(adminKeys.order(order.id), order)
    },
  })
}

export function useDeleteOrder(): UseMutationResult<TableSummary, unknown, number> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId) => client.deleteOrder(orderId),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

// ---------- Tables ----------

export function useTables(): UseQueryResult<TableInfo[]> {
  const client = useApiClient()
  return useQuery({
    queryKey: adminKeys.tables(),
    queryFn: () => client.listTables(),
  })
}

export function useRegisterTable(): UseMutationResult<
  TableInfo,
  unknown,
  { tableNumber: number; password: string }
> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req) => client.registerTable(req),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

export function useEndSession(): UseMutationResult<SessionSummary, unknown, number> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tableId) => client.endSession(tableId),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

export function useTableHistory(
  tableId: number | null,
  range: { from?: string; to?: string },
  options: { enabled?: boolean } = {},
): UseQueryResult<HistoryOrder[]> {
  const client = useApiClient()
  const { from, to } = range
  return useQuery({
    queryKey: adminKeys.history(tableId ?? -1, from, to),
    queryFn: () => client.getTableHistory(tableId as number, { from, to }),
    enabled: tableId != null && (options.enabled ?? true),
  })
}

// ---------- Menus ----------

export function useAdminMenus(): UseQueryResult<CategoryMenus[]> {
  const client = useApiClient()
  return useQuery({
    queryKey: adminKeys.menus(),
    queryFn: () => client.listAdminMenus(),
  })
}

export function useCreateMenu(): UseMutationResult<Menu, unknown, MenuInput> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input) => client.createMenu(input),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

export function useUpdateMenu(): UseMutationResult<
  Menu,
  unknown,
  { menuId: number; input: MenuInput }
> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ menuId, input }) => client.updateMenu(menuId, input),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

export function useDeleteMenu(): UseMutationResult<void, unknown, number> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (menuId) => client.deleteMenu(menuId),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}

export function useReorderMenus(): UseMutationResult<
  void,
  unknown,
  { category: string; orderedIds: number[] }
> {
  const client = useApiClient()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ category, orderedIds }) => client.reorderMenus(category, orderedIds),
    retry: false,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all })
    },
  })
}
