import { useProviders, useProviderModels } from '../../hooks/useProviders'
import {
  PROVIDER_SELECT_LABEL,
  PROVIDER_MODEL_SELECT_LABEL,
  PROVIDER_NO_MODELS,
  PROVIDER_STATUS_SUFFIX_UNAVAILABLE,
  PROVIDER_AUTO_DEFAULT,
  PROVIDER_MODEL_AUTO_FIRST,
  MSG_LOADING,
} from '../../constants/strings'

interface Props {
  providerId: string | null
  modelId: string | null
  onChange: (providerId: string | null, modelId: string | null) => void
  className?: string
}

export function ProviderModelSelect({ providerId, modelId, onChange, className = '' }: Props) {
  const { providers } = useProviders()
  const { models, loading: modelsLoading } = useProviderModels(providerId)

  const visionModels = models.filter(model => model.vision)

  return (
    <div className={`flex gap-3 ${className}`}>
      <label className="flex flex-col gap-1 text-sm flex-1">
        <span className="font-medium text-gray-700">{PROVIDER_SELECT_LABEL}</span>
        <select
          value={providerId ?? ''}
          onChange={event => {
            const selectedId = event.target.value || null
            onChange(selectedId, null)
          }}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">{PROVIDER_AUTO_DEFAULT}</option>
          {providers.map(provider => (
            <option key={provider.id} value={provider.id} disabled={!provider.available}>
              {provider.name} {provider.available ? '' : PROVIDER_STATUS_SUFFIX_UNAVAILABLE}
            </option>
          ))}
        </select>
      </label>

      {providerId && (
        <label className="flex flex-col gap-1 text-sm flex-1">
          <span className="font-medium text-gray-700">{PROVIDER_MODEL_SELECT_LABEL}</span>
          <select
            value={modelId ?? ''}
            onChange={event => onChange(providerId, event.target.value || null)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
            disabled={modelsLoading}
          >
            <option value="">{modelsLoading ? MSG_LOADING : PROVIDER_MODEL_AUTO_FIRST}</option>
            {visionModels.length === 0 && !modelsLoading && (
              <option disabled>{PROVIDER_NO_MODELS}</option>
            )}
            {visionModels.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  )
}
