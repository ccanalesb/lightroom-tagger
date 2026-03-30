import { useState } from 'react'

interface AsyncThumbnailProps {
  src: string
  alt: string
  fallback?: string
  className?: string
}

export function AsyncThumbnail({ src, alt, fallback = '--', className = '' }: AsyncThumbnailProps) {
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

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
      <img
        src={src}
        alt={alt}
        className={`w-full h-full object-cover ${errored ? 'hidden' : ''} ${loaded ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)}
      />
    </div>
  )
}
