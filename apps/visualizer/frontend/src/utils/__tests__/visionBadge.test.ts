import { describe, it, expect } from 'vitest'
import { visionBadgeClasses } from '../visionBadge'

describe('visionBadgeClasses', () => {
  it('returns green for SAME', () => {
    const result = visionBadgeClasses('SAME')
    expect(result).toContain('bg-green')
    expect(result).toContain('text-green')
  })

  it('returns red for DIFFERENT', () => {
    const result = visionBadgeClasses('DIFFERENT')
    expect(result).toContain('bg-red')
    expect(result).toContain('text-red')
  })

  it('returns yellow for UNCERTAIN', () => {
    const result = visionBadgeClasses('UNCERTAIN')
    expect(result).toContain('bg-yellow')
    expect(result).toContain('text-yellow')
  })

  it('defaults to UNCERTAIN for unknown values', () => {
    expect(visionBadgeClasses('UNKNOWN')).toBe(visionBadgeClasses('UNCERTAIN'))
  })

  it('defaults to UNCERTAIN for undefined via fallback', () => {
    expect(visionBadgeClasses(undefined)).toBe(visionBadgeClasses('UNCERTAIN'))
  })
})
