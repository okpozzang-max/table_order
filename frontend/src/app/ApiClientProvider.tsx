import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { ApiClientContext } from '../shared/api/client'
import type { ApiClient } from '../shared/api/client'
import { createRealClient } from '../shared/api/realClient'
import { createSharedMockClient } from '../mocks/mockClient'

export type ApiMode = 'mock' | 'real'

export function currentApiMode(): ApiMode {
  return import.meta.env.VITE_API_MODE === 'real' ? 'real' : 'mock'
}

export function createApiClient(mode: ApiMode = currentApiMode()): ApiClient {
  return mode === 'real' ? createRealClient() : createSharedMockClient()
}

export function ApiClientProvider({ client, children }: { client?: ApiClient; children: ReactNode }) {
  const value = useMemo(() => client ?? createApiClient(), [client])
  return <ApiClientContext.Provider value={value}>{children}</ApiClientContext.Provider>
}
