import { useCallback, type Dispatch, type SetStateAction } from 'react'
import type { Match, MatchGroup } from '../services/api'

export function appendMatchGroupsPage(
  prev: MatchGroup[],
  incoming: MatchGroup[] | undefined,
): MatchGroup[] {
  const next = [...prev]
  for (const g of incoming ?? []) {
    const idx = next.findIndex((existing) => existing.instagram_key === g.instagram_key)
    if (idx >= 0) next[idx] = g
    else next.push(g)
  }
  return next
}

export function applyValidationChange(
  groups: MatchGroup[],
  match: Match,
  validated: boolean,
): MatchGroup[] {
  return groups.map((group) => {
    if (group.instagram_key !== match.instagram_key) return group
    const candidates = group.candidates.map((candidate) =>
      candidate.catalog_key === match.catalog_key && candidate.instagram_key === match.instagram_key
        ? { ...candidate, validated_at: validated ? new Date().toISOString() : undefined }
        : candidate,
    )
    return {
      ...group,
      candidates,
      has_validated: candidates.some((candidate) => candidate.validated_at),
    }
  })
}

export function applyRejected(groups: MatchGroup[], match: Match): MatchGroup[] {
  return groups.flatMap((group) => {
    if (group.instagram_key !== match.instagram_key) return [group]
    const remaining = group.candidates.filter(
      (candidate) =>
        !(
          candidate.catalog_key === match.catalog_key &&
          candidate.instagram_key === match.instagram_key
        ),
    )
    if (remaining.length === 0) {
      return [
        {
          ...group,
          candidates: [],
          candidate_count: 0,
          best_score: 0,
          has_validated: false,
          all_rejected: true,
        },
      ]
    }
    return [
      {
        ...group,
        candidates: remaining,
        candidate_count: remaining.length,
        best_score: Math.max(...remaining.map((candidate) => candidate.score)),
        has_validated: remaining.some((candidate) => candidate.validated_at),
      },
    ]
  })
}

export function useMatchGroupMutations(
  setMatchGroups: Dispatch<SetStateAction<MatchGroup[]>>,
) {
  const handleValidationChange = useCallback(
    (match: Match, validated: boolean) => {
      setMatchGroups((prev) => applyValidationChange(prev, match, validated))
    },
    [setMatchGroups],
  )

  const handleRejected = useCallback(
    (match: Match) => {
      setMatchGroups((prev) => applyRejected(prev, match))
    },
    [setMatchGroups],
  )

  return { handleValidationChange, handleRejected }
}
