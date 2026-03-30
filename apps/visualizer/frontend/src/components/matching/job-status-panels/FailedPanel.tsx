import {
  MATCHING_FAILED,
  MATCHING_FAILED_UNKNOWN,
  MATCHING_DISMISS,
} from '../../../constants/strings';

export function FailedPanel({ error, onDismiss }: { error?: string | null; onDismiss: () => void }) {
  return (
    <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          <div>
            <p className="font-medium text-red-900">{MATCHING_FAILED}</p>
            <p className="text-sm text-red-700">{error || MATCHING_FAILED_UNKNOWN}</p>
          </div>
        </div>
        <button onClick={onDismiss} className="text-red-700 hover:text-red-900">
          {MATCHING_DISMISS}
        </button>
      </div>
    </div>
  );
}
