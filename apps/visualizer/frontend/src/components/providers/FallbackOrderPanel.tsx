import type { Provider } from '../../services/api'
import {
  PROVIDER_FALLBACK_HEADING,
  PROVIDER_FALLBACK_DESCRIPTION,
  PROVIDER_STATUS_SUFFIX_UNAVAILABLE,
  PROVIDER_MOVE_UP,
  PROVIDER_MOVE_DOWN,
} from '../../constants/strings'

interface Props {
  providers: Provider[]
  order: string[]
  onReorder: (order: string[]) => void
}

function reorderBySwappingNeighbors(
  currentOrder: string[],
  index: number,
  direction: 'up' | 'down',
): string[] {
  const neighborIndex = direction === 'up' ? index - 1 : index + 1
  if (neighborIndex < 0 || neighborIndex >= currentOrder.length) {
    return currentOrder
  }
  const nextOrder = [...currentOrder]
  const temporary = nextOrder[index]
  nextOrder[index] = nextOrder[neighborIndex]
  nextOrder[neighborIndex] = temporary
  return nextOrder
}

export function FallbackOrderPanel({ providers, order, onReorder }: Props) {
  const providerMap = Object.fromEntries(providers.map(provider => [provider.id, provider]))

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm p-4">
      <h3 className="font-semibold text-gray-900 mb-1">{PROVIDER_FALLBACK_HEADING}</h3>
      <p className="text-sm text-gray-500 mb-3">{PROVIDER_FALLBACK_DESCRIPTION}</p>
      <ol className="space-y-1.5">
        {order.map((providerId, index) => {
          const provider = providerMap[providerId]
          const isFirst = index === 0
          const isLast = index === order.length - 1
          return (
            <li key={providerId} className="flex items-center gap-2 text-sm">
              <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold">
                {index + 1}
              </span>
              <span className="font-medium text-gray-800 flex-1 min-w-0">
                {provider?.name ?? providerId}
              </span>
              {provider && !provider.available && (
                <span className="text-xs text-gray-400">{PROVIDER_STATUS_SUFFIX_UNAVAILABLE}</span>
              )}
              <span className="flex items-center gap-0.5 shrink-0">
                <button
                  type="button"
                  disabled={isFirst}
                  aria-label={PROVIDER_MOVE_UP}
                  onClick={() => {
                    onReorder(reorderBySwappingNeighbors(order, index, 'up'))
                  }}
                  className="px-1.5 py-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  ↑
                </button>
                <button
                  type="button"
                  disabled={isLast}
                  aria-label={PROVIDER_MOVE_DOWN}
                  onClick={() => {
                    onReorder(reorderBySwappingNeighbors(order, index, 'down'))
                  }}
                  className="px-1.5 py-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  ↓
                </button>
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
