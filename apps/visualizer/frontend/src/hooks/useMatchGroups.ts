import { useState, useCallback } from 'react'
import type { MatchGroup } from '../services/api'
import { MatchingAPI } from '../services/api'
import { appendMatchGroupsPage, useMatchGroupMutations } from './matchGroupMutations'

export function useMatchGroups() {
  const [matchGroups, setMatchGroups] = useState<MatchGroup[]>([])
  const [total, setTotal] = useState(0)
  const { handleValidationChange, handleRejected } = useMatchGroupMutations(setMatchGroups)

  const fetchGroups = useCallback(
    async (
      limit = 100,
      offset = 0,
      params?: { sort_by_date?: 'newest' | 'oldest' },
    ) => {
      const data = await MatchingAPI.list(limit, offset, params)
      if (offset === 0) {
        setMatchGroups(data.match_groups ?? [])
        setTotal(data.total_groups ?? data.total)
      } else {
        setMatchGroups((prev) => appendMatchGroupsPage(prev, data.match_groups))
      }
    },
    [],
  )

  return { matchGroups, total, fetchGroups, handleValidationChange, handleRejected }
}
