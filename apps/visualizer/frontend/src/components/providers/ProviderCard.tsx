import type { Provider, ProviderModel } from '../../services/api'
import {
  PROVIDER_STATUS_AVAILABLE,
  PROVIDER_STATUS_UNAVAILABLE,
  PROVIDER_MODELS_HEADING,
  PROVIDER_NO_MODELS,
} from '../../constants/strings'
import { ModelList } from './ModelList'
import { AddModelForm } from './AddModelForm'

interface ProviderCardProps {
  provider: Provider
  models: ProviderModel[]
  expanded: boolean
  onToggle: () => void
  onAddModel: (model: { id: string; name: string; vision: boolean }) => Promise<void>
  onRemoveModel: (modelId: string) => void
}

export function ProviderCard({
  provider,
  models,
  expanded,
  onToggle,
  onAddModel,
  onRemoveModel,
}: ProviderCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900">{provider.name}</h3>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              provider.available
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {provider.available ? PROVIDER_STATUS_AVAILABLE : PROVIDER_STATUS_UNAVAILABLE}
          </span>
        </div>
        <span className="text-gray-400 text-sm">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          <h4 className="text-sm font-medium text-gray-700 mb-2">{PROVIDER_MODELS_HEADING}</h4>
          {models.length === 0 ? (
            <p className="text-sm text-gray-400">{PROVIDER_NO_MODELS}</p>
          ) : (
            <ModelList models={models} onRemove={onRemoveModel} />
          )}
          <AddModelForm onAdd={onAddModel} />
        </div>
      )}
    </div>
  )
}
