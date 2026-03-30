import {
  DESC_ERROR_RATE_LIMIT,
  DESC_ERROR_AUTH,
  DESC_ERROR_UNAVAILABLE,
  DESC_ERROR_GENERIC,
} from '../constants/strings'

export function classifyApiError(err: unknown): string {
  const message = err instanceof Error ? err.message : ''
  if (message.includes('429')) return DESC_ERROR_RATE_LIMIT
  if (message.includes('401')) return DESC_ERROR_AUTH
  if (message.includes('503')) return DESC_ERROR_UNAVAILABLE
  return DESC_ERROR_GENERIC
}
