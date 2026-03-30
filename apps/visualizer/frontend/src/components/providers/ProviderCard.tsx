import type { Provider, ProviderModel } from '../../services/api'
import {
  PROVIDER_STATUS_AVAILABLE,
  PROVIDER_STATUS_UNAVAILABLE,
  PROVIDER_MODELS_HEADING,
  PROVIDER_NO_MODELS,
  PROVIDER_COL_MODEL,
  PROVIDER_COL_VISION,
  PROVIDER_COL_SOURCE,
  PROVIDER_SOURCE_CONFIG,
  PROVIDER_SOURCE_DISCOVERED,
  PROVIDER_SOURCE_USER,
} from '../../constants/strings'

const SOURCE_LABELS: Record<string, string> = {
  config: PROVIDER_SOURCE_CONFIG,
  discovered: PROVIDER_SOURCE_DISCOVERED,
  user: PROVIDER_SOURCE_USER,
}

interface Props {
  provider: Provider
  models: ProviderModel[]
  expanded: boolean
  onToggle: () => void
}

export function ProviderCard({ provider, models, expanded, onToggle }: Props) {
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
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 text-xs uppercase tracking-wider">
                  <th className="pb-1">{PROVIDER_COL_MODEL}</th>
                  <th className="pb-1">{PROVIDER_COL_VISION}</th>
                  <th className="pb-1">{PROVIDER_COL_SOURCE}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {models.map(model => (
                  <tr key={model.id}>
                    <td className="py-1.5 font-mono text-xs text-gray-800">{model.name}</td>
                    <td className="py-1.5">
                      {model.vision ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-1.5 text-xs text-gray-500">
                      {SOURCE_LABELS[model.source] ?? model.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
