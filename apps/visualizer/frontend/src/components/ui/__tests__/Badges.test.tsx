import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImageTypeBadge, StatusBadge, VisionBadge } from '../badges'

describe('ImageTypeBadge', () => {
  it('should render CAT for catalog type', () => {
    render(<ImageTypeBadge type="catalog" />)
    expect(screen.getByText('CAT')).toBeTruthy()
  })

  it('should render IG for instagram type', () => {
    render(<ImageTypeBadge type="instagram" />)
    expect(screen.getByText('IG')).toBeTruthy()
  })

  it('should apply blue classes for catalog', () => {
    const { container } = render(<ImageTypeBadge type="catalog" />)
    expect(container.firstElementChild!.className).toContain('bg-blue')
  })

  it('should apply pink classes for instagram', () => {
    const { container } = render(<ImageTypeBadge type="instagram" />)
    expect(container.firstElementChild!.className).toContain('bg-pink')
  })
})

describe('StatusBadge', () => {
  it('should render the status label', () => {
    render(<StatusBadge status="completed" />)
    expect(screen.getByText('Completed')).toBeTruthy()
  })

  it('should apply appropriate color classes', () => {
    const { container } = render(<StatusBadge status="failed" />)
    expect(container.firstElementChild!.className).toMatch(/bg-red-50|text-error/)
  })

  it('should render with border when requested', () => {
    const { container } = render(<StatusBadge status="running" withBorder />)
    expect(container.firstElementChild!.className).toContain('border-2')
    expect(container.firstElementChild!.className).toContain('border-blue')
  })
})

describe('VisionBadge', () => {
  it('should render the vision result text', () => {
    render(<VisionBadge result="SAME" />)
    expect(screen.getByText('SAME')).toBeTruthy()
  })

  it('should apply success styling for SAME', () => {
    const { container } = render(<VisionBadge result="SAME" />)
    expect(container.firstElementChild!.className).toMatch(/bg-green-50|text-success/)
  })

  it('should apply error styling for DIFFERENT', () => {
    const { container } = render(<VisionBadge result="DIFFERENT" />)
    expect(container.firstElementChild!.className).toMatch(/bg-red-50|text-error/)
  })

  it('should default to UNCERTAIN styling for undefined', () => {
    const { container } = render(<VisionBadge result={undefined} />)
    expect(screen.getByText('UNCERTAIN')).toBeTruthy()
    expect(container.firstElementChild!.className).toMatch(/bg-orange-50|text-warning/)
  })
})
