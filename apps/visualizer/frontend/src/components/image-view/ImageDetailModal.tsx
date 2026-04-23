import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import type { ImageView } from '../../services/api'
import { ImagesAPI } from '../../services/api'
import { useBodyScrollLock, useFocusTrap } from '../../hooks'
import { IMAGE_DETAILS_TITLE } from '../../constants/strings'
import { CatalogImageDetailSections } from './CatalogImageDetailSections'
import { InstagramImageDetailSections } from './InstagramImageDetailSections'
import { ImageMetadataBadges, type PrimaryScoreSource } from './ImageMetadataBadges'
import { ModalCloseButton } from './ModalCloseButton'
import { ErrorBoundary, ErrorState, invalidate, invalidateAll, useQuery } from '../../data'

interface ImageDetailModalProps {
  imageType: 'catalog' | 'instagram'
  imageKey: string
  /** Optional list-row data shown instantly while the detail call is in
   *  flight; once the detail payload arrives it overrides this. */
  initialImage?: ImageView
  /** Header primary-score source (CONTEXT Q3). */
  primaryScoreSource: PrimaryScoreSource
  /** When set, catalog detail calls request `?score_perspective=<slug>`
   *  so the header pill shows the same slug the tile used. */
  scorePerspectiveSlug?: string
  onClose: () => void
}

function ImageDetailModalFallback({
  initialImage,
  imageKey,
  imageType,
  primaryScoreSource,
}: {
  initialImage?: ImageView
  imageKey: string
  imageType: 'catalog' | 'instagram'
  primaryScoreSource: PrimaryScoreSource
}) {
  return (
    <div className="grid gap-6 p-6 md:grid-cols-2">
      <div className="aspect-square overflow-hidden rounded-base bg-surface">
        <img
          src={`/api/images/${imageType}/${encodeURIComponent(imageKey)}/thumbnail`}
          alt={initialImage?.filename ?? imageKey}
          className="h-full w-full object-contain"
        />
      </div>

      <div className="space-y-6">
        {initialImage ? (
          <ImageMetadataBadges image={initialImage} primaryScoreSource={primaryScoreSource} />
        ) : null}

        <p className="text-sm text-text-tertiary" role="status" aria-live="polite">
          Loading image details…
        </p>
      </div>
    </div>
  )
}

function ImageDetailModalBody({
  imageType,
  imageKey,
  primaryScoreSource,
  scorePerspectiveSlug,
}: Omit<ImageDetailModalProps, 'initialImage' | 'onClose'>) {
  const detailKey = [
    'images.detail',
    imageType,
    imageKey,
    scorePerspectiveSlug ?? '',
  ] as const

  const image = useQuery(detailKey, () =>
    ImagesAPI.getImageDetail(
      imageType,
      imageKey,
      scorePerspectiveSlug ? { score_perspective: scorePerspectiveSlug } : undefined,
    ),
  )

  const [, bump] = useState(0)
  const handleDataChanged = useCallback(() => {
    invalidate(detailKey)
    bump((n) => n + 1)
  }, [detailKey])

  return (
    <div className="grid gap-6 p-6 md:grid-cols-2">
      <div className="aspect-square overflow-hidden rounded-base bg-surface">
        <img
          src={`/api/images/${imageType}/${encodeURIComponent(imageKey)}/thumbnail`}
          alt={image?.filename ?? imageKey}
          className="h-full w-full object-contain"
        />
      </div>

      <div className="space-y-6">
        <ImageMetadataBadges image={image} primaryScoreSource={primaryScoreSource} />

        {image.image_type === 'catalog' ? (
          <CatalogImageDetailSections image={image} onDataChanged={handleDataChanged} />
        ) : null}
        {image.image_type === 'instagram' ? (
          <InstagramImageDetailSections image={image} onDataChanged={handleDataChanged} />
        ) : null}
      </div>
    </div>
  )
}

/**
 * The single entry point for viewing any image in detail. Every tile in
 * the app opens this modal with just `{ imageType, imageKey }` so the
 * modal can re-fetch from the authoritative detail endpoint and avoid
 * the zero-score stubs the legacy modals relied on.
 *
 * Responsive (CONTEXT Q4):
 *   - `<md` (<768px): full-screen sheet at `100dvh`.
 *   - `>=md`: centered card, `max-h-[min(90vh,900px)]`.
 *
 * Accessibility (CONTEXT):
 *   - `role="dialog" aria-modal="true"` + `aria-labelledby`.
 *   - Focus trap via `useFocusTrap` (in-repo, no new dependency).
 *   - Scroll lock via `useBodyScrollLock`.
 *   - ESC closes; backdrop click closes.
 */
export function ImageDetailModal({
  imageType,
  imageKey,
  initialImage,
  primaryScoreSource,
  scorePerspectiveSlug,
  onClose,
}: ImageDetailModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const titleId = `image-detail-modal-title-${imageKey.replace(/[^a-zA-Z0-9_-]/g, '_')}`

  useBodyScrollLock(true)
  useFocusTrap(dialogRef, true)

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 backdrop-blur-sm md:flex md:items-center md:justify-center md:p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative flex h-[100dvh] max-h-[100dvh] w-full flex-col overflow-hidden bg-bg shadow-deep md:h-auto md:max-h-[min(90vh,900px)] md:max-w-4xl md:rounded-card"
        style={{ backgroundColor: 'var(--color-background)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div
            className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-border bg-bg px-6 py-4 md:rounded-t-card"
            style={{ backgroundColor: 'var(--color-background)' }}
          >
            <h2 id={titleId} className="text-card-title text-text truncate">
              {IMAGE_DETAILS_TITLE}
            </h2>
            <ModalCloseButton onClick={onClose} />
          </div>

          <ErrorBoundary
            resetKeys={[imageType, imageKey, scorePerspectiveSlug ?? '']}
            fallback={({ error, reset }) => (
              <div className="p-6">
                <ErrorState
                  error={error}
                  reset={() => {
                    invalidateAll(['images.detail', imageType, imageKey])
                    reset()
                  }}
                />
              </div>
            )}
          >
            <Suspense
              fallback={
                <ImageDetailModalFallback
                  initialImage={initialImage}
                  imageKey={imageKey}
                  imageType={imageType}
                  primaryScoreSource={primaryScoreSource}
                />
              }
            >
              <ImageDetailModalBody
                imageType={imageType}
                imageKey={imageKey}
                primaryScoreSource={primaryScoreSource}
                scorePerspectiveSlug={scorePerspectiveSlug}
              />
            </Suspense>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}
