import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMatchGroups } from '../useMatchGroups'
import type { Match, MatchGroup } from '../../services/api'

const listMock = vi.fn()

vi.mock('../../services/api', () => ({
  MatchingAPI: {
    list: (...args: unknown[]) => listMock(...args),
  },
}))

function makeMatch(partial: Partial<Match> & Pick<Match, 'instagram_key' | 'catalog_key'>): Match {
  return {
    score: 0.9,
    ...partial,
  }
}

describe('useMatchGroups handleRejected tombstone', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('keeps total unchanged when the last candidate is rejected (tombstone path)', async () => {
    const instaKey = 'insta-1'
    const group: MatchGroup = {
      instagram_key: instaKey,
      candidates: [makeMatch({ instagram_key: instaKey, catalog_key: 'cat-a', score: 0.9 })],
      candidate_count: 1,
      best_score: 0.9,
      has_validated: false,
    }

    listMock.mockResolvedValueOnce({
      total: 10,
      total_groups: 10,
      match_groups: [group],
      matches: [],
    })

    const { result } = renderHook(() => useMatchGroups())

    await act(async () => {
      await result.current.fetchGroups(100, 0)
    })

    expect(result.current.total).toBe(10)
    expect(result.current.matchGroups).toHaveLength(1)

    const totalBeforeFinalReject = result.current.total

    await act(async () => {
      result.current.handleRejected(
        makeMatch({ instagram_key: instaKey, catalog_key: 'cat-a', score: 0.9 }),
      )
    })

    expect(result.current.total).toBe(totalBeforeFinalReject)
    const updated = result.current.matchGroups[0]
    expect(updated?.candidates).toEqual([])
    expect(updated?.all_rejected).toBe(true)
    expect(updated?.candidate_count).toBe(0)
    expect(updated?.best_score).toBe(0)
    expect(updated?.has_validated).toBe(false)
  })
})
