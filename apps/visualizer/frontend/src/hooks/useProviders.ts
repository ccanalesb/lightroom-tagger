import { useCallback, useReducer } from 'react'
import { invalidateAll, useQuery } from '../data'
import { ProvidersAPI, type Provider, type ProviderModel } from '../services/api'

const EMPTY_PROVIDER_BUNDLE: { providers: Provider[]; fallbackOrder: string[] } = {
  providers: [],
  fallbackOrder: [],
}

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
  const bundle = useQuery(['providers.list', 'hook', rev] as const, fetchProviderBundle, {
    initialValue: EMPTY_PROVIDER_BUNDLE,
  })

  const refresh = useCallback(() => {
    invalidateAll(['providers.list'])
    bump()
  }, [])

  const updateFallbackOrder = useCallback(async (order: string[]) => {
    await ProvidersAPI.updateFallbackOrder(order)
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
    { initialValue: [] },
  )

  return { models, loading: false, error: null }
}
