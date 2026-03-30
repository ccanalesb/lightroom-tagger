import { useState, useEffect } from 'react'
import { ProvidersAPI, type ProviderModel } from '../services/api'
import { useProviders } from '../hooks/useProviders'
import { ProviderCard, FallbackOrderPanel } from '../components/providers'
import { PageLoading, PageError } from '../components/ui/page-states'
import { PROVIDER_TITLE } from '../constants/strings'

export function ProvidersPage() {
  const { providers, fallbackOrder, loading, error } = useProviders()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [modelCache, setModelCache] = useState<Record<string, ProviderModel[]>>({})

  useEffect(() => {
    if (!expandedId || modelCache[expandedId]) return
    ProvidersAPI.listModels(expandedId).then(models => {
      setModelCache(prev => ({ ...prev, [expandedId]: models }))
    })
  }, [expandedId, modelCache])

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
            onToggle={() => setExpandedId(prev => (prev === provider.id ? null : provider.id))}
          />
        ))}
      </div>

      <FallbackOrderPanel providers={providers} order={fallbackOrder} />
    </div>
  )
}
