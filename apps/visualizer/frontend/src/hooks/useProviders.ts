import { useState, useEffect, useCallback } from 'react'
import { ProvidersAPI, type Provider, type ProviderModel } from '../services/api'

export function useProviders() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [fallbackOrder, setFallbackOrder] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [providerList, fallback] = await Promise.all([
        ProvidersAPI.list(),
        ProvidersAPI.getFallbackOrder(),
      ])
      setProviders(providerList)
      setFallbackOrder(fallback.order)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const updateFallbackOrder = useCallback(async (order: string[]) => {
    await ProvidersAPI.updateFallbackOrder(order)
    await refresh()
  }, [refresh])

  return { providers, fallbackOrder, loading, error, refresh, updateFallbackOrder }
}

export function useProviderModels(providerId: string | null) {
  const [models, setModels] = useState<ProviderModel[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!providerId) {
      setModels([])
      return
    }
    setLoading(true)
    ProvidersAPI.listModels(providerId)
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setLoading(false))
  }, [providerId])

  return { models, loading }
}
