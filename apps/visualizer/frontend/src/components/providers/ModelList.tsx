import type { ProviderModel } from '../../services/api'
import {
  PROVIDER_COL_MODEL,
  PROVIDER_COL_VISION,
  PROVIDER_COL_SOURCE,
  PROVIDER_SOURCE_CONFIG,
  PROVIDER_SOURCE_DISCOVERED,
  PROVIDER_SOURCE_USER,
  PROVIDER_REMOVE_MODEL,
  PROVIDER_COL_ACTIONS,
} from '../../constants/strings'

const SOURCE_LABELS: Record<string, string> = {
  config: PROVIDER_SOURCE_CONFIG,
  discovered: PROVIDER_SOURCE_DISCOVERED,
  user: PROVIDER_SOURCE_USER,
}

interface ModelListProps {
  models: ProviderModel[]
  onRemove: (modelId: string) => void
}

export function ModelList({ models, onRemove }: ModelListProps) {
  const hasUserModels = models.some(model => model.source === 'user')

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-gray-500 text-xs uppercase tracking-wider">
          <th className="pb-1">{PROVIDER_COL_MODEL}</th>
          <th className="pb-1">{PROVIDER_COL_VISION}</th>
          <th className="pb-1">{PROVIDER_COL_SOURCE}</th>
          {hasUserModels && (
            <th className="pb-1 w-10 text-right font-normal">{PROVIDER_COL_ACTIONS}</th>
          )}
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
            {hasUserModels && (
              <td className="py-1.5 text-right">
                {model.source === 'user' ? (
                  <button
                    type="button"
                    onClick={() => onRemove(model.id)}
                    aria-label={PROVIDER_REMOVE_MODEL}
                    className="text-gray-400 hover:text-red-600 text-base leading-none px-1"
                  >
                    ×
                  </button>
                ) : null}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
