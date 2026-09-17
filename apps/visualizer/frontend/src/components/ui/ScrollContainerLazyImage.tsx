import { useEffect, useRef, useState, type RefObject } from 'react'

interface ScrollContainerLazyImageProps {
  scrollContainerRef: RefObject<HTMLElement | null>
  src: string
  alt: string
  className?: string
  onLoad?: () => void
  onError?: () => void
}

/**
 * Loads a thumbnail when it intersects a horizontal (or vertical) scroll
 * container. Native `loading="lazy"` does not reliably fire for elements
 * inside `overflow-x-auto` rails, so we observe against the rail root.
 */
export function ScrollContainerLazyImage({
  scrollContainerRef,
  src,
  alt,
  className,
  onLoad,
  onError,
}: ScrollContainerLazyImageProps) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [shouldLoad, setShouldLoad] = useState(false)

  useEffect(() => {
    const target = imgRef.current
    if (!target) return

    if (typeof IntersectionObserver === 'undefined') {
      setShouldLoad(true)
      return
    }

    const root = scrollContainerRef.current
    if (!root) {
      setShouldLoad(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldLoad(true)
          observer.disconnect()
        }
      },
      { root, rootMargin: '100px' },
    )
    observer.observe(target)
    return () => observer.disconnect()
  }, [scrollContainerRef, src])

  return (
    <img
      ref={imgRef}
      src={shouldLoad ? src : undefined}
      alt={alt}
      decoding="async"
      className={className}
      onLoad={onLoad}
      onError={onError}
    />
  )
}
