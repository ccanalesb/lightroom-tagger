import { useCallback, useReducer } from 'react'
import { invalidateAll, useQuery } from '../data'
import { ProvidersAPI, type Provider, type ProviderModel } from '../services/api'

async function fetchProviderBundle(): Promise<{
  providers: Provider[]
  fallbackOrder: string[]
}> {
  const [providerList, fallback] = await Promise.all([
    ProvidersAPI.list(),
    ProvidersAPI.getFallbackOrder(),
  ])
  return { providers: providerList, fallbackOrder: fallback.order }
}

export function useProviders() {
  const [rev, bump] = useReducer((n: number) => n + 1, 0)
  const bundle = useQuery(['providers.list', 'hook', rev] as const, fetchProviderBundle)

  const refresh = useCallback(() => {
    invalidateAll(['providers.list'])
    bump()
  }, [])

  const updateFallbackOrder = useCallback(async (order: string[]) => {
    await ProvidersAPI.updateFallbackOrder(order)
    invalidateAll(['providers.list'])
    bump()
  }, [])

  return {
    providers: bundle.providers,
    fallbackOrder: bundle.fallbackOrder,
    loading: false,
    error: null,
    refresh,
    updateFallbackOrder,
  }
}

export function useProviderModels(providerId: string | null) {
  const models = useQuery(
    ['providers.models', providerId] as const,
    async (): Promise<ProviderModel[]> => {
      if (!providerId) return []
      return ProvidersAPI.listModels(providerId)
    },
  )

  return { models, loading: false, error: null }
}
