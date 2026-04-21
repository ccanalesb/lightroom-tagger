import { BestPhotosGrid } from '../components/identity/BestPhotosGrid'
import { PostNextSuggestionsPanel } from '../components/identity/PostNextSuggestionsPanel'
import { StyleFingerprintPanel } from '../components/identity/StyleFingerprintPanel'
import { IDENTITY_PAGE_SUBTITLE, IDENTITY_PAGE_TITLE } from '../constants/strings'

export function IdentityPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-section text-text mb-2">{IDENTITY_PAGE_TITLE}</h1>
        <p className="text-text-secondary">{IDENTITY_PAGE_SUBTITLE}</p>
      </div>

      <StyleFingerprintPanel />
      <BestPhotosGrid />
      <PostNextSuggestionsPanel />
    </div>
  )
}
