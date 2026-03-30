import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AsyncThumbnail } from '../AsyncThumbnail'

describe('AsyncThumbnail', () => {
  it('renders an img element with the given src', () => {
    render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const img = screen.getByRole('img')
    expect(img.getAttribute('src')).toBe('/img.jpg')
    expect(img.getAttribute('alt')).toBe('test')
  })

  it('starts with pulse placeholder visible', () => {
    const { container } = render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).toBeTruthy()
  })

  it('hides pulse and shows image after load', () => {
    const { container } = render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const img = screen.getByRole('img')
    fireEvent.load(img)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).toBeNull()
  })

  it('shows fallback text on error', () => {
    render(<AsyncThumbnail src="/bad.jpg" alt="test" fallback="--" />)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(screen.getByText('--')).toBeTruthy()
  })

  it('hides img element on error', () => {
    render(<AsyncThumbnail src="/bad.jpg" alt="test" />)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(img.className).toContain('hidden')
  })
})
