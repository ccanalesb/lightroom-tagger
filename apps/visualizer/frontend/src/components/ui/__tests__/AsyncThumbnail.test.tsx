import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AsyncThumbnail } from '../AsyncThumbnail'

describe('AsyncThumbnail', () => {
  it('should render an img element with the given src', () => {
    render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const img = screen.getByRole('img')
    expect(img.getAttribute('src')).toBe('/img.jpg')
    expect(img.getAttribute('alt')).toBe('test')
  })

  it('should start with pulse placeholder visible', () => {
    const { container } = render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).toBeTruthy()
  })

  it('should hide pulse and show image after load', () => {
    const { container } = render(<AsyncThumbnail src="/img.jpg" alt="test" />)
    const img = screen.getByRole('img')
    fireEvent.load(img)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).toBeNull()
  })

  it('should show fallback text on error', () => {
    render(<AsyncThumbnail src="/bad.jpg" alt="test" fallback="--" />)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(screen.getByText('--')).toBeTruthy()
  })

  it('should hide img element on error', () => {
    render(<AsyncThumbnail src="/bad.jpg" alt="test" />)
    const img = screen.getByRole('img')
    fireEvent.error(img)
    expect(img.className).toContain('hidden')
  })
})
