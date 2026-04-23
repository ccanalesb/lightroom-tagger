import { query } from './query'

export function useQuery<T>(key: readonly unknown[], fetcher: () => Promise<T>): T {
  return query(key, fetcher)
}
