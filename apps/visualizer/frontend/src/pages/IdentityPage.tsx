import { Suspense } from 'react'
import { BestPhotosGrid } from '../components/identity/BestPhotosGrid'
import { PostNextSuggestionsPanel } from '../components/identity/PostNextSuggestionsPanel'
import { StyleFingerprintPanel } from '../components/identity/StyleFingerprintPanel'
import { SkeletonGrid } from '../components/ui/page-states'
import { IDENTITY_PAGE_SUBTITLE, IDENTITY_PAGE_TITLE } from '../constants/strings'
import { ErrorBoundary, ErrorState, invalidate, invalidateAll } from '../data'

export function IdentityPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-section text-text mb-2">{IDENTITY_PAGE_TITLE}</h1>
        <p className="text-text-secondary">{IDENTITY_PAGE_SUBTITLE}</p>
      </div>

      <ErrorBoundary
        fallback={({ error, reset }) => (
          <ErrorState
            error={error}
            reset={() => {
              invalidate(['identity', 'style-fingerprint'])
              reset()
            }}
          />
        )}
      >
        <Suspense fallback={<SkeletonGrid count={6} />}>
          <StyleFingerprintPanel />
        </Suspense>
      </ErrorBoundary>

      <ErrorBoundary
        fallback={({ error, reset }) => (
          <ErrorState
            error={error}
            reset={() => {
              invalidateAll(['identity', 'best-photos'])
              reset()
            }}
          />
        )}
      >
        <Suspense fallback={<SkeletonGrid count={6} />}>
          <BestPhotosGrid />
        </Suspense>
      </ErrorBoundary>

      <ErrorBoundary
        fallback={({ error, reset }) => (
          <ErrorState
            error={error}
            reset={() => {
              invalidateAll(['identity', 'post-next'])
              reset()
            }}
          />
        )}
      >
        <Suspense fallback={<SkeletonGrid count={6} />}>
          <PostNextSuggestionsPanel />
        </Suspense>
      </ErrorBoundary>
    </div>
  )
}
