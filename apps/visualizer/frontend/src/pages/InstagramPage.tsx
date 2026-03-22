import { useEffect, useState, useCallback } from 'react'
import { ImagesAPI, InstagramImage } from '../services/api'
import {
  MSG_ERROR_PREFIX,
  INSTAGRAM_DOWNLOADED,
} from '../constants/strings'

const ITEMS_PER_PAGE = 48

export function InstagramPage() {
  const [images, setImages] = useState<InstagramImage[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [pagination, setPagination] = useState({
    current_page: 1,
    total_pages: 1,
    has_more: false,
  })
  const [dateFilter, setDateFilter] = useState('') // Format: YYYYMM
  const [availableMonths, setAvailableMonths] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  
  // Modal state
  const [selectedImage, setSelectedImage] = useState<InstagramImage | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Extract available months from images
  const extractMonths = useCallback((imgs: InstagramImage[]) => {
    const months = new Set<string>()
    imgs.forEach(img => {
      if (img.instagram_folder) {
        months.add(img.instagram_folder)
      }
    })
    return Array.from(months).sort().reverse() // Newest first
  }, [])

  const fetchImages = useCallback(async (newOffset: number = 0) => {
    setIsLoading(true)
    try {
      const params: { limit: number; offset: number; date_folder?: string } = {
        limit: ITEMS_PER_PAGE,
        offset: newOffset,
      }
      
      if (dateFilter) {
        params.date_folder = dateFilter
      }
      
      const data = await ImagesAPI.listInstagram(params)
      
      setImages(data.images)
      setTotal(data.total)
      setPagination(data.pagination)
      setOffset(newOffset)
      setError(null)
      
      // Extract available months on first load
      if (availableMonths.length === 0 && data.images.length > 0) {
        // We need to get all images to extract months, so let's do a separate call
        const allData = await ImagesAPI.listInstagram({ limit: 10000, offset: 0 })
        setAvailableMonths(extractMonths(allData.images))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [dateFilter, availableMonths.length, extractMonths])

  useEffect(() => {
    fetchImages(0)
  }, [fetchImages])

  const handlePrevPage = () => {
    if (offset > 0) {
      fetchImages(Math.max(0, offset - ITEMS_PER_PAGE))
    }
  }

  const handleNextPage = () => {
    if (pagination.has_more) {
      fetchImages(offset + ITEMS_PER_PAGE)
    }
  }

  const handleDateFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setDateFilter(e.target.value)
    setOffset(0)
    // fetchImages will be called by useEffect when dateFilter changes
  }

  const clearDateFilter = () => {
    setDateFilter('')
    setOffset(0)
  }
  
  const handleImageClick = (image: InstagramImage) => {
    setSelectedImage(image)
    setIsModalOpen(true)
  }
  
  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedImage(null)
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with filters */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl font-bold text-gray-900">
          {INSTAGRAM_DOWNLOADED}
        </h2>
        
        <div className="flex items-center gap-3">
          {/* Date Filter */}
          <div className="flex items-center gap-2">
            <select
              value={dateFilter}
              onChange={handleDateFilterChange}
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All dates</option>
              {availableMonths.map(month => (
                <option key={month} value={month}>
                  {formatMonth(month)}
                </option>
              ))}
            </select>
            {dateFilter && (
              <button
                onClick={clearDateFilter}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                Clear
              </button>
            )}
          </div>
          
          <p className="text-sm text-gray-500">
            {total} images
          </p>
        </div>
      </div>

      {/* Image Grid */}
      {isLoading && images.length === 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <ImageSkeleton key={i} />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {images.map((image) => (
              <InstagramImageCard 
                key={image.key} 
                image={image} 
                onClick={() => handleImageClick(image)}
              />
            ))}
          </div>

          {/* Pagination */}
          {pagination.total_pages > 1 && (
            <div className="flex items-center justify-between pt-6 border-t border-gray-200">
              <button
                onClick={handlePrevPage}
                disabled={offset === 0 || isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ← Previous
              </button>
              
              <div className="text-sm text-gray-600">
                Page {pagination.current_page} of {pagination.total_pages}
                <span className="text-gray-400 mx-2">|</span>
                Showing {offset + 1}-{Math.min(offset + ITEMS_PER_PAGE, total)} of {total}
              </div>
              
              <button
                onClick={handleNextPage}
                disabled={!pagination.has_more || isLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
      
      {/* Metadata Modal */}
      {isModalOpen && selectedImage && (
        <ImageMetadataModal 
          image={selectedImage} 
          onClose={handleCloseModal} 
        />
      )}
    </div>
  )
}

// Helper function to format YYYYMM to readable date
function formatMonth(yyyymm: string): string {
  if (yyyymm.length !== 6) return yyyymm
  
  const year = yyyymm.substring(0, 4)
  const month = yyyymm.substring(4, 6)
  
  const date = new Date(parseInt(year), parseInt(month) - 1)
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
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

function InstagramImageCard({ image, onClick }: { image: InstagramImage; onClick: () => void }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`

  return (
    <div 
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group bg-white cursor-pointer"
      onClick={onClick}
    >
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
        {/* Info overlay on hover */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white text-sm font-medium">Click for details</span>
        </div>
      </div>
      <div className="p-2">
        <div className="flex items-start justify-between gap-1">
          <div className="flex flex-col min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate" title={image.instagram_folder}>
              {image.instagram_folder}
            </p>
            <p className="text-[10px] text-gray-500 uppercase truncate" title={image.source_folder}>
              {image.source_folder}
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(image.crawled_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  )
}

function ImageMetadataModal({ image, onClose }: { image: InstagramImage; onClose: () => void }) {
  const [imageData, setImageData] = useState<InstagramImage | null>(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    // Fetch full image data including any additional metadata
    const fetchImageData = async () => {
      try {
        // For now, use the passed image data
        // In the future, we could fetch additional details from the API
        setImageData(image)
      } catch (err) {
        console.error('Error fetching image data:', err)
      } finally {
        setLoading(false)
      }
    }
    
    fetchImageData()
  }, [image])
  
  // Handle click outside to close
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }
  
  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])
  
  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])
  
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`
  
  return (
    <div 
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Image Details</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Modal Content */}
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
          ) : imageData ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Image Preview */}
              <div className="space-y-4">
                <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
                  <img
                    src={thumbnailUrl}
                    alt={imageData.filename}
                    className="w-full h-full object-contain"
                  />
                </div>
                
                {/* Quick Actions */}
                <div className="flex gap-2">
                  {imageData.post_url ? (
                    <a
                      href={imageData.post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 bg-blue-600 text-white text-center py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                    >
                      View on Instagram
                    </a>
                  ) : (
                    <button
                      onClick={() => window.open(`file://${imageData.local_path}`, '_blank')}
                      className="flex-1 bg-gray-600 text-white text-center py-2 px-4 rounded-md hover:bg-gray-700 transition-colors text-sm font-medium"
                    >
                      Open Local File
                    </button>
                  )}
                </div>
              </div>
              
              {/* Metadata */}
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Basic Information
                  </h4>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                    <MetadataRow label="Filename" value={imageData.filename} />
                    <MetadataRow label="Media Key" value={imageData.key} />
                    <MetadataRow label="Source Folder" value={imageData.source_folder} />
                    <MetadataRow label="Date Folder" value={imageData.instagram_folder} />
                    <MetadataRow 
                      label="Added" 
                      value={new Date(imageData.crawled_at).toLocaleString()} 
                    />
                  </div>
                </div>
                
                {imageData.image_hash && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Image Analysis
                    </h4>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <MetadataRow 
                        label="Visual Hash (pHash)" 
                        value={imageData.image_hash} 
                        monospace
                      />
                      <p className="text-xs text-gray-500 mt-2">
                        This hash is used to detect visually identical images across your collection.
                      </p>
                    </div>
                  </div>
                )}
                
                {imageData.description && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Caption
                    </h4>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">
                        {imageData.description}
                      </p>
                    </div>
                  </div>
                )}
                
                {/* File Path */}
                <div>
                  <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    File Location
                  </h4>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <code className="text-xs text-gray-600 break-all">
                      {imageData.local_path}
                    </code>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
        
        {/* Modal Footer */}
        <div className="border-t border-gray-200 p-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function MetadataRow({ label, value, monospace = false }: { label: string; value: string; monospace?: boolean }) {
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between sm:gap-4">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-sm text-gray-900 text-right ${monospace ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  )
}
