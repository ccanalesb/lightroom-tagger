import {
  MATCHING_COMPLETED,
  MATCHING_COMPLETED_MATCHES,
  MATCHING_DISMISS,
} from '../../../constants/strings';

export function CompletedPanel({ matches, onDismiss }: { matches: number; onDismiss: () => void }) {
  return (
    <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <div>
            <p className="font-medium text-green-900">{MATCHING_COMPLETED}</p>
            <p className="text-sm text-green-700">
              {matches} {MATCHING_COMPLETED_MATCHES}
            </p>
          </div>
        </div>
        <button onClick={onDismiss} className="text-green-700 hover:text-green-900">
          {MATCHING_DISMISS}
        </button>
      </div>
    </div>
  );
}
