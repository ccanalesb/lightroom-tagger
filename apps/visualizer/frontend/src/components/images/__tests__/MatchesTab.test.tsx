import { Suspense } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MatchesTab } from '../MatchesTab'
import { MatchingAPI, type Match, type MatchGroup } from '../../../services/api'
import { deleteMatching } from '../../../data/cache'
import { msgMatchGroupCandidates } from '../../../constants/strings'

function makeMatch(catalogKey: string, instaKey: string): Match {
  return {
    instagram_key: instaKey,
    catalog_key: catalogKey,
    score: 0.9,
    total_score: 0.9,
  }
}

function makeGroup(
  instaKey: string,
  candidates: Match[],
  overrides?: Partial<MatchGroup>,
): MatchGroup {
  const best = Math.max(0, ...candidates.map((c) => c.total_score ?? c.score ?? 0))
  return {
    instagram_key: instaKey,
    candidates,
    best_score: best,
    candidate_count: candidates.length,
    has_validated: false,
    all_rejected: false,
    ...overrides,
  }
}

describe('MatchesTab stack-wide match status', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
  })

  it('shows multi-candidate count when stack apply produced several catalog rows', async () => {
    const igKey = '202603/ig1'
    const group = makeGroup(igKey, [
      makeMatch('cat/rep.jpg', igKey),
      makeMatch('cat/m1.jpg', igKey),
      makeMatch('cat/m2.jpg', igKey),
    ])

    vi.spyOn(MatchingAPI, 'list').mockResolvedValue({
      total: 1,
      total_groups: 1,
      total_matches: 3,
      match_groups: [group],
      matches: group.candidates,
    })

    render(
      <Suspense fallback={<div>loading</div>}>
        <MatchesTab />
      </Suspense>,
    )

    expect(await screen.findByText(msgMatchGroupCandidates(3))).toBeInTheDocument()
  })

  it('shows partial candidate count after conflict-skipped stack apply', async () => {
    const igKey = '202603/ig_conflict'
    const group = makeGroup(igKey, [makeMatch('cat/rep.jpg', igKey), makeMatch('cat/ok.jpg', igKey)])

    vi.spyOn(MatchingAPI, 'list').mockResolvedValue({
      total: 1,
      total_groups: 1,
      total_matches: 2,
      match_groups: [group],
      matches: group.candidates,
    })

    render(
      <Suspense fallback={<div>loading</div>}>
        <MatchesTab />
      </Suspense>,
    )

    expect(await screen.findByText(msgMatchGroupCandidates(2))).toBeInTheDocument()
  })
})
