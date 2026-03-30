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
    expect(container.firstElementChild!.className).toContain('bg-red')
  })

  it('should render with border when requested', () => {
    const { container } = render(<StatusBadge status="running" withBorder />)
    expect(container.firstElementChild!.className).toContain('border-blue')
  })
})

describe('VisionBadge', () => {
  it('should render the vision result text', () => {
    render(<VisionBadge result="SAME" />)
    expect(screen.getByText('SAME')).toBeTruthy()
  })

  it('should apply green for SAME', () => {
    const { container } = render(<VisionBadge result="SAME" />)
    expect(container.firstElementChild!.className).toContain('bg-green')
  })

  it('should apply red for DIFFERENT', () => {
    const { container } = render(<VisionBadge result="DIFFERENT" />)
    expect(container.firstElementChild!.className).toContain('bg-red')
  })

  it('should default to UNCERTAIN styling for undefined', () => {
    const { container } = render(<VisionBadge result={undefined} />)
    expect(screen.getByText('UNCERTAIN')).toBeTruthy()
    expect(container.firstElementChild!.className).toContain('bg-yellow')
  })
})
