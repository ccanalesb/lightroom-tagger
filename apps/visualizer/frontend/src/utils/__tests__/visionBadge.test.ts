import { describe, it, expect } from 'vitest'
import { visionBadgeClasses } from '../visionBadge'

describe('visionBadgeClasses', () => {
  it('should return green for SAME', () => {
    const result = visionBadgeClasses('SAME')
    expect(result).toContain('bg-green')
    expect(result).toContain('text-green')
  })

  it('should return red for DIFFERENT', () => {
    const result = visionBadgeClasses('DIFFERENT')
    expect(result).toContain('bg-red')
    expect(result).toContain('text-red')
  })

  it('should return yellow for UNCERTAIN', () => {
    const result = visionBadgeClasses('UNCERTAIN')
    expect(result).toContain('bg-yellow')
    expect(result).toContain('text-yellow')
  })

  it('should default to UNCERTAIN for unknown values', () => {
    expect(visionBadgeClasses('UNKNOWN')).toBe(visionBadgeClasses('UNCERTAIN'))
  })

  it('should default to UNCERTAIN for undefined via fallback', () => {
    expect(visionBadgeClasses(undefined)).toBe(visionBadgeClasses('UNCERTAIN'))
  })
})
