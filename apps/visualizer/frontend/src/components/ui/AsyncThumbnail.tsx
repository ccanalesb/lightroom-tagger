import { useState, type RefObject } from 'react'
import { ScrollContainerLazyImage } from './ScrollContainerLazyImage'

interface AsyncThumbnailProps {
  src: string
  alt: string
  fallback?: string
  className?: string
  /** Pass the scroll container ref when rendered inside a horizontal rail so
   *  thumbnails load via IntersectionObserver instead of native lazy loading. */
  scrollContainerRef?: RefObject<HTMLElement | null>
}

export function AsyncThumbnail({
  src,
  alt,
  fallback = '--',
  className = '',
  scrollContainerRef,
}: AsyncThumbnailProps) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

  const imgClassName = `w-full h-full object-cover ${errored ? 'hidden' : ''} ${loaded ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`

  return (
    <div className={`relative bg-gray-100 ${className}`}>
      {!loaded && !errored && (
        <div className="absolute inset-0 bg-gray-200 animate-pulse" />
      )}
      {errored && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs text-gray-400">{fallback}</span>
        </div>
      )}
      {scrollContainerRef ? (
        <ScrollContainerLazyImage
          scrollContainerRef={scrollContainerRef}
          src={src}
          alt={alt}
          className={imgClassName}
          onLoad={() => setLoaded(true)}
          onError={() => setErrored(true)}
        />
      ) : (
        <img
          src={src}
          alt={alt}
          className={imgClassName}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setErrored(true)}
        />
      )}
    </div>
  )
}
