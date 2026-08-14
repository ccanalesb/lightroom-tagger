import { StackSuggestionsPanel } from '../components/stacks/StackSuggestionsPanel'
import { ErrorBoundary } from '../components/ui/ErrorBoundary'
import {
  STACK_SUGGESTIONS_PAGE_SUBTITLE,
  STACK_SUGGESTIONS_PAGE_TITLE,
} from '../constants/strings'

export function StackSuggestionsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">{STACK_SUGGESTIONS_PAGE_TITLE}</h1>
        <p className="text-text-secondary">{STACK_SUGGESTIONS_PAGE_SUBTITLE}</p>
      </div>
      <ErrorBoundary>
        <StackSuggestionsPanel />
      </ErrorBoundary>
    </div>
  )
}
