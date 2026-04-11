import { useState, useEffect, useCallback } from 'react';
import { ProvidersAPI, type ProviderModel } from '../../services/api';
import { useProviders } from '../../hooks/useProviders';
import { ProviderCard, FallbackOrderPanel } from '../providers';
import { Card } from '../ui/Card';

export function ProvidersTab() {
  const { providers, fallbackOrder, loading, error, updateFallbackOrder } = useProviders();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [modelCache, setModelCache] = useState<Record<string, ProviderModel[]>>({});
  const [reachability, setReachability] = useState<Record<string, boolean | null>>({});
  const [connectionErrors, setConnectionErrors] = useState<Record<string, string | undefined>>({});

  const refreshModelsForProvider = useCallback(async (providerId: string) => {
    const models = await ProvidersAPI.listModels(providerId);
    setModelCache(previous => ({ ...previous, [providerId]: models }));
  }, []);

  useEffect(() => {
    if (!expandedId || modelCache[expandedId]) return;
    refreshModelsForProvider(expandedId).catch(console.error);
  }, [expandedId, modelCache, refreshModelsForProvider]);

  useEffect(() => {
    if (providers.length === 0) return;
    let cancelled = false;
    Promise.all(
      providers.map(provider =>
        ProvidersAPI.health(provider.id)
          .then(response => ({
            id: provider.id,
            reachable: response.reachable,
            detail: response.reachable ? undefined : response.error,
          }))
          .catch(err => ({
            id: provider.id,
            reachable: false,
            detail: err instanceof Error ? err.message : String(err),
          })),
      ),
    ).then(results => {
      if (cancelled) return;
      setReachability(prev => {
        const next = { ...prev };
        for (const row of results) {
          next[row.id] = row.reachable;
        }
        return next;
      });
      setConnectionErrors(prev => {
        const next = { ...prev };
        for (const row of results) {
          if (row.detail) next[row.id] = row.detail;
          else delete next[row.id];
        }
        return next;
      });
    });
    return () => {
      cancelled = true;
    };
  }, [providers]);

  const handleAddModel = useCallback(
    async (providerId: string, model: { id: string; name: string; vision: boolean }) => {
      await ProvidersAPI.addModel(providerId, model);
      await refreshModelsForProvider(providerId);
    },
    [refreshModelsForProvider],
  );

  const handleRemoveModel = useCallback(
    async (providerId: string, modelId: string) => {
      await ProvidersAPI.removeModel(providerId, modelId);
      await refreshModelsForProvider(providerId);
    },
    [refreshModelsForProvider],
  );

  const handleReorderModel = useCallback(
    async (providerId: string, modelId: string, direction: 'up' | 'down') => {
      const models = modelCache[providerId] ?? [];
      const index = models.findIndex(m => m.id === modelId);
      if (index === -1) return;

      const newModels = [...models];
      const targetIndex = direction === 'up' ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= newModels.length) return;

      [newModels[index], newModels[targetIndex]] = [newModels[targetIndex], newModels[index]];
      const newOrder = newModels.map(m => m.id);

      setModelCache(previous => ({ ...previous, [providerId]: newModels }));
      
      try {
        await ProvidersAPI.reorderModels(providerId, newOrder);
      } catch (error) {
        await refreshModelsForProvider(providerId);
      }
    },
    [modelCache, refreshModelsForProvider],
  );

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">Loading providers...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-error">Error: {error}</div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-card-title text-text mb-2">AI Model Providers</h3>
        <p className="text-sm text-text-secondary">
          Configure vision model providers and manage fallback order
        </p>
      </div>

      <div className="space-y-3">
        {providers.map(provider => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            models={modelCache[provider.id] ?? []}
            expanded={expandedId === provider.id}
            onToggle={() => setExpandedId(previous => (previous === provider.id ? null : provider.id))}
            onAddModel={model => handleAddModel(provider.id, model)}
            onRemoveModel={modelId => {
              handleRemoveModel(provider.id, modelId).catch(console.error);
            }}
            onReorderModel={(modelId, direction) => {
              handleReorderModel(provider.id, modelId, direction).catch(console.error);
            }}
            connectionReachable={reachability[provider.id] ?? null}
            connectionError={connectionErrors[provider.id] ?? null}
          />
        ))}
      </div>

      <FallbackOrderPanel
        providers={providers}
        order={fallbackOrder}
        onReorder={order => {
          updateFallbackOrder(order).catch(console.error);
        }}
      />
    </div>
  );
}
