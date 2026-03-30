import { describe, it, expect } from 'vitest'
import { statusBadgeClasses, progressBarColor } from '../jobStatus'

describe('statusBadgeClasses', () => {
  it('returns green classes for completed', () => {
    const result = statusBadgeClasses('completed')
    expect(result).toContain('bg-green')
    expect(result).toContain('text-green')
  })

  it('returns red classes for failed', () => {
    const result = statusBadgeClasses('failed')
    expect(result).toContain('bg-red')
    expect(result).toContain('text-red')
  })

  it('returns blue classes for running', () => {
    const result = statusBadgeClasses('running')
    expect(result).toContain('bg-blue')
    expect(result).toContain('text-blue')
  })

  it('returns gray classes for cancelled', () => {
    const result = statusBadgeClasses('cancelled')
    expect(result).toContain('bg-gray')
    expect(result).toContain('text-gray')
  })

  it('defaults to yellow for pending/unknown', () => {
    expect(statusBadgeClasses('pending')).toContain('bg-yellow')
    expect(statusBadgeClasses('unknown')).toContain('bg-yellow')
  })

  it('includes border classes when withBorder is true', () => {
    const result = statusBadgeClasses('completed', { withBorder: true })
    expect(result).toContain('border-green')
  })

  it('does not include border classes by default', () => {
    const result = statusBadgeClasses('completed')
    expect(result).not.toContain('border-')
  })
})

describe('progressBarColor', () => {
  it('returns green for completed', () => {
    expect(progressBarColor('completed')).toContain('bg-green')
  })

  it('returns red for failed', () => {
    expect(progressBarColor('failed')).toContain('bg-red')
  })

  it('returns blue for running', () => {
    expect(progressBarColor('running')).toContain('bg-blue')
  })

  it('returns gray for unknown status', () => {
    expect(progressBarColor('whatever')).toContain('bg-gray')
  })
})
