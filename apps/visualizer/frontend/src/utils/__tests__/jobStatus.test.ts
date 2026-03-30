import { describe, it, expect } from 'vitest'
import { statusBadgeClasses, progressBarColor } from '../jobStatus'

describe('statusBadgeClasses', () => {
  it('should return green classes for completed', () => {
    const result = statusBadgeClasses('completed')
    expect(result).toContain('bg-green')
    expect(result).toContain('text-green')
  })

  it('should return red classes for failed', () => {
    const result = statusBadgeClasses('failed')
    expect(result).toContain('bg-red')
    expect(result).toContain('text-red')
  })

  it('should return blue classes for running', () => {
    const result = statusBadgeClasses('running')
    expect(result).toContain('bg-blue')
    expect(result).toContain('text-blue')
  })

  it('should return gray classes for cancelled', () => {
    const result = statusBadgeClasses('cancelled')
    expect(result).toContain('bg-gray')
    expect(result).toContain('text-gray')
  })

  it('should default to yellow for pending/unknown', () => {
    expect(statusBadgeClasses('pending')).toContain('bg-yellow')
    expect(statusBadgeClasses('unknown')).toContain('bg-yellow')
  })

  it('should include border classes when withBorder is true', () => {
    const result = statusBadgeClasses('completed', { withBorder: true })
    expect(result).toContain('border-green')
  })

  it('should not include border classes by default', () => {
    const result = statusBadgeClasses('completed')
    expect(result).not.toContain('border-')
  })
})

describe('progressBarColor', () => {
  it('should return green for completed', () => {
    expect(progressBarColor('completed')).toContain('bg-green')
  })

  it('should return red for failed', () => {
    expect(progressBarColor('failed')).toContain('bg-red')
  })

  it('should return blue for running', () => {
    expect(progressBarColor('running')).toContain('bg-blue')
  })

  it('should return gray for unknown status', () => {
    expect(progressBarColor('whatever')).toContain('bg-gray')
  })
})
