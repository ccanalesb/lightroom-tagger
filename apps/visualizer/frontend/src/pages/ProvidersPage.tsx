import { useState, useEffect, useCallback } from 'react'
import { ProvidersAPI, type ProviderModel } from '../services/api'
import { useProviders } from '../hooks/useProviders'
import { ProviderCard, FallbackOrderPanel } from '../components/providers'
import { PageLoading, PageError } from '../components/ui/page-states'
import { PROVIDER_TITLE } from '../constants/strings'

export function ProvidersPage() {
  const { providers, fallbackOrder, loading, error, updateFallbackOrder } = useProviders()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [modelCache, setModelCache] = useState<Record<string, ProviderModel[]>>({})

  const refreshModelsForProvider = useCallback(async (providerId: string) => {
    const models = await ProvidersAPI.listModels(providerId)
    setModelCache(previous => ({ ...previous, [providerId]: models }))
  }, [])

  useEffect(() => {
    if (!expandedId || modelCache[expandedId]) return
    refreshModelsForProvider(expandedId).catch(console.error)
  }, [expandedId, modelCache, refreshModelsForProvider])

  const handleAddModel = useCallback(
    async (providerId: string, model: { id: string; name: string; vision: boolean }) => {
      await ProvidersAPI.addModel(providerId, model)
      await refreshModelsForProvider(providerId)
    },
    [refreshModelsForProvider],
  )

  const handleRemoveModel = useCallback(
    async (providerId: string, modelId: string) => {
      await ProvidersAPI.removeModel(providerId, modelId)
      await refreshModelsForProvider(providerId)
    },
    [refreshModelsForProvider],
  )

  if (loading) return <PageLoading />
  if (error) return <PageError message={error} />

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">{PROVIDER_TITLE}</h2>

      <div className="space-y-3">
        {providers.map(provider => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            models={modelCache[provider.id] ?? []}
            expanded={expandedId === provider.id}
            onToggle={() => setExpandedId(previous => (previous === provider.id ? null : provider.id))}
            onAddModel={model => {
              handleAddModel(provider.id, model).catch(console.error)
            }}
            onRemoveModel={modelId => {
              handleRemoveModel(provider.id, modelId).catch(console.error)
            }}
          />
        ))}
      </div>

      <FallbackOrderPanel
        providers={providers}
        order={fallbackOrder}
        onReorder={order => {
          updateFallbackOrder(order).catch(console.error)
        }}
      />
    </div>
  )
}
