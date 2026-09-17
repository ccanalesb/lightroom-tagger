import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { useRef } from 'react'
import { ScrollContainerLazyImage } from '../ScrollContainerLazyImage'

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

function Harness({ src }: { src: string }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  return (
    <div ref={scrollRef} data-testid="scroll-root" className="overflow-x-auto">
      <ScrollContainerLazyImage
        scrollContainerRef={scrollRef}
        src={src}
        alt="test thumbnail"
        className="h-full w-full object-cover"
      />
    </div>
  )
}

describe('ScrollContainerLazyImage', () => {
  beforeEach(() => {
    MockIntersectionObserver.instances = []
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('does not set src until the image intersects the scroll container', () => {
    render(<Harness src="/api/images/catalog/foo/thumbnail" />)

    const img = screen.getByRole('img', { name: 'test thumbnail' })
    expect(img).not.toHaveAttribute('src')

    const observer = MockIntersectionObserver.instances[0]
    expect(observer.observe).toHaveBeenCalledWith(img)
    act(() => {
      observer.trigger(true, img)
    })
    expect(img).toHaveAttribute('src', '/api/images/catalog/foo/thumbnail')
  })

  it('loads immediately when IntersectionObserver is unavailable', () => {
    vi.unstubAllGlobals()
    vi.stubGlobal('IntersectionObserver', undefined)

    render(<Harness src="/api/images/catalog/bar/thumbnail" />)

    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/images/catalog/bar/thumbnail')
  })
})
