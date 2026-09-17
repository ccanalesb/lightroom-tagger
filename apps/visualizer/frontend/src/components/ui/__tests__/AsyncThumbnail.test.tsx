import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { useRef } from 'react'
import { AsyncThumbnail } from '../AsyncThumbnail'

type IoCallback = IntersectionObserverCallback

class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = []
  callback: IoCallback
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()

  constructor(callback: IoCallback) {
    this.callback = callback
    MockIntersectionObserver.instances.push(this)
  }

  trigger(isIntersecting: boolean, target: Element) {
    this.callback(
      [{ isIntersecting, target } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    )
  }
}

function ThumbnailInScroller() {
  const scrollRef = useRef<HTMLDivElement>(null)
  return (
    <div ref={scrollRef} data-testid="scroll-root" className="overflow-x-auto">
      <AsyncThumbnail src="/img.jpg" alt="test" scrollContainerRef={scrollRef} />
    </div>
  )
}

describe('AsyncThumbnail', () => {
  beforeEach(() => {
    MockIntersectionObserver.instances = []
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defers src until intersection when scrollContainerRef is set', () => {
    render(<ThumbnailInScroller />)

    const img = screen.getByRole('img')
    expect(img).not.toHaveAttribute('src')
    expect(img).not.toHaveAttribute('loading')

    const observer = MockIntersectionObserver.instances[0]
    act(() => {
      observer.trigger(true, img)
    })
    expect(img).toHaveAttribute('src', '/img.jpg')
  })

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
