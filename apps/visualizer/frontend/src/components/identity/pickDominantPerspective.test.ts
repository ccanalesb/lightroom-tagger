import { describe, it, expect } from 'vitest'
import type { IdentityPerPerspectiveScore } from '../../services/api'
import { pickDominantPerspective } from './pickDominantPerspective'

function score(
  perspective_slug: string,
  display_name: string,
  scoreVal: number,
): IdentityPerPerspectiveScore {
  return {
    perspective_slug,
    display_name,
    score: scoreVal,
    prompt_version: 'v1',
    model_used: 'm',
    scored_at: 't',
    rationale_preview: '',
  }
}

describe('pickDominantPerspective', () => {
  it('returns the entry with the highest score', () => {
    const result = pickDominantPerspective([
      {
        perspective_slug: 'street',
        display_name: 'Street',
        score: 9,
        prompt_version: 'v1',
        model_used: 'm',
        scored_at: 't',
        rationale_preview: '',
      },
      score('documentary', 'Documentary', 7),
    ])
    expect(result?.perspective_slug).toBe('street')
  })

  it('returns null for an empty array', () => {
    expect(pickDominantPerspective([])).toBeNull()
  })

  it('returns null for undefined', () => {
    expect(pickDominantPerspective(undefined)).toBeNull()
  })

  it('on a tie, keeps the first entry (index 0)', () => {
    const result = pickDominantPerspective([
      score('street', 'Street', 8),
      score('documentary', 'Documentary', 8),
    ])
    expect(result?.perspective_slug).toBe('street')
  })
})
