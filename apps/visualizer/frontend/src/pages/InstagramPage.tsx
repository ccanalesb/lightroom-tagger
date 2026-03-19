import { useEffect, useState } from 'react'
import { ImagesAPI, InstagramImage } from '../services/api'
import {
  MSG_ERROR_PREFIX,
  MSG_NO_IMAGES,
  INSTAGRAM_DOWNLOADED,
} from '../constants/strings'

export function InstagramPage() {
  const [images, setImages] = useState<InstagramImage[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function fetchImages() {
      try {
        const data = await ImagesAPI.listInstagram(100)
        if (mounted) {
          setImages(data.images)
          setTotal(data.total)
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      }
    }

    fetchImages()
    return () => { mounted = false }
  }, [])

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-gray-900">
          {INSTAGRAM_DOWNLOADED}
        </h2>
        <p className="text-sm text-gray-500">
          {total} images
        </p>
      </div>

      {images.length === 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <ImageSkeleton key={i} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {images.map((image) => (
            <InstagramImageCard key={image.key} image={image} />
          ))}
        </div>
      )}
    </div>
  )
}

function ImageSkeleton() {
  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      <div className="aspect-square bg-gray-200 animate-pulse" />
      <div className="p-2 space-y-1">
        <div className="h-3 bg-gray-200 rounded animate-pulse" />
        <div className="h-2 bg-gray-200 rounded w-2/3 animate-pulse" />
      </div>
    </div>
  )
}

function InstagramImageCard({ image }: { image: InstagramImage }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`
  
  // Instagram carousel URL with specific image index
  const postUrlWithIndex = `${image.post_url}?img_index=${image.image_index - 1}`

  return (
    <div className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group bg-white">
      <div className="aspect-square bg-gray-100 relative">
        {!loaded && !error && (
          <div className="absolute inset-0 bg-gray-200 animate-pulse" />
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <span className="text-xs text-gray-400">Error</span>
          </div>
        )}
        <img
          src={thumbnailUrl}
          alt={image.filename}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
        {image.total_in_post > 1 && (
          <div className="absolute top-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            {image.image_index}/{image.total_in_post}
          </div>
        )}
      </div>
      <div className="p-2">
        <div className="flex items-start justify-between gap-1">
          <p className="text-xs font-medium text-gray-900 truncate" title={image.instagram_folder}>
            {image.instagram_folder}
          </p>
          <a
            href={postUrlWithIndex}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:underline flex-shrink-0"
          >
            View
          </a>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(image.crawled_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  )
}