import { describe, it, expect } from 'vitest'
import { formatDateTime, formatDate, formatTime, formatMonth } from '../date'

describe('formatDateTime', () => {
  it('formats ISO string to locale datetime', () => {
    const result = formatDateTime('2026-03-15T14:30:00.000Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns empty string for undefined', () => {
    expect(formatDateTime(undefined)).toBe('')
  })

  it('returns empty string for null', () => {
    expect(formatDateTime(null)).toBe('')
  })
})

describe('formatDate', () => {
  it('formats ISO string to locale date', () => {
    const result = formatDate('2026-03-15T14:30:00.000Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns empty string for falsy input', () => {
    expect(formatDate(undefined)).toBe('')
    expect(formatDate(null)).toBe('')
    expect(formatDate('')).toBe('')
  })
})

describe('formatTime', () => {
  it('formats ISO string to locale time', () => {
    const result = formatTime('2026-03-15T14:30:00.000Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns empty string for falsy input', () => {
    expect(formatTime(undefined)).toBe('')
  })
})

describe('formatMonth', () => {
  it('formats YYYYMM to readable month string', () => {
    const result = formatMonth('202603')
    expect(result).toContain('2026')
    expect(result).toContain('March')
  })

  it('returns input as-is when not 6 chars', () => {
    expect(formatMonth('2026')).toBe('2026')
    expect(formatMonth('')).toBe('')
  })
})
