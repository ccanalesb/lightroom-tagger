import type { Provider } from '../../services/api'
import {
  PROVIDER_FALLBACK_HEADING,
  PROVIDER_FALLBACK_DESCRIPTION,
  PROVIDER_STATUS_SUFFIX_UNAVAILABLE,
} from '../../constants/strings'

interface Props {
  providers: Provider[]
  order: string[]
}

export function FallbackOrderPanel({ providers, order }: Props) {
  const providerMap = Object.fromEntries(providers.map(provider => [provider.id, provider]))

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4">
      <h3 className="font-semibold text-gray-900 mb-1">{PROVIDER_FALLBACK_HEADING}</h3>
      <p className="text-sm text-gray-500 mb-3">{PROVIDER_FALLBACK_DESCRIPTION}</p>
      <ol className="space-y-1.5">
        {order.map((providerId, index) => {
          const provider = providerMap[providerId]
          return (
            <li key={providerId} className="flex items-center gap-2 text-sm">
              <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold">
                {index + 1}
              </span>
              <span className="font-medium text-gray-800">{provider?.name ?? providerId}</span>
              {provider && !provider.available && (
                <span className="text-xs text-gray-400">{PROVIDER_STATUS_SUFFIX_UNAVAILABLE}</span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
