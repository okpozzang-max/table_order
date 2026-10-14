import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AdminAuthProvider } from '../admin'
import { CartProvider, TableAuthProvider } from '../customer'
import type { ApiClient } from '../shared/api/client'
import { ToastProvider } from '../shared/ui'
import { ApiClientProvider } from './ApiClientProvider'
import { AppRoutes } from './AppRoutes'
import { createQueryClient } from './queryClient'
import { useState } from 'react'

/** 라우터 아래에서 인증/장바구니 상태를 제공한다. (테스트에서는 MemoryRouter 아래에 재사용) */
export function AppStateProviders({ children }: { children: ReactNode }) {
  return (
    <TableAuthProvider>
      <CartProvider>
        <AdminAuthProvider>{children}</AdminAuthProvider>
      </CartProvider>
    </TableAuthProvider>
  )
}

/**
 * 앱 루트. 중첩 순서: ApiClient > QueryClient > Toast > Router > TableAuth > Cart > AdminAuth.
 * 고객 인증은 저장된 자격 증명이 있을 때만 서버를 호출하므로(관리자 PC에는 없음) 전역으로 둔다.
 */
export function App({ client }: { client?: ApiClient }) {
  const [queryClient] = useState(createQueryClient)
  return (
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <BrowserRouter>
            <AppStateProviders>
              <AppRoutes />
            </AppStateProviders>
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ApiClientProvider>
  )
}
