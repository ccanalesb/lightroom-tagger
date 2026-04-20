import {
  MODAL_CLOSE,
  MATCHING_RESULTS,
  MATCH_VALIDATE,
  MATCH_VALIDATED,
  MATCH_REJECT,
  MATCH_DETAIL_UNVALIDATE_FIRST,
} from '../../../constants/strings';

interface MatchDetailHeaderProps {
  validated: boolean;
  busy: boolean;
  onValidate: () => void;
  onReject: () => void;
  onClose: () => void;
}

/**
 * Sticky header for the match review modal: title plus the three
 * action buttons (Validate / Reject / Close). Extracted so
 * `MatchDetailModal.tsx` stays focused on state + layout.
 */
export function MatchDetailHeader({
  validated,
  busy,
  onValidate,
  onReject,
  onClose,
}: MatchDetailHeaderProps) {
  return (
    <div className="sticky top-0 z-10 bg-white rounded-t-lg flex flex-wrap justify-between items-center p-4 border-b gap-3">
      <div className="flex items-center gap-2 min-w-0">
        <h3 className="text-lg font-bold text-gray-900">{MATCHING_RESULTS}</h3>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={onValidate}
          disabled={busy || validated}
          className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
            validated
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'border border-green-600 text-green-600 hover:bg-green-50'
          } ${busy || validated ? 'opacity-60 cursor-not-allowed' : ''}`}
        >
          {validated ? `\u2713 ${MATCH_VALIDATED}` : MATCH_VALIDATE}
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={busy || validated}
          className={`px-3 py-1 rounded text-sm font-medium border transition-colors ${
            validated
              ? 'border-gray-300 text-gray-300 cursor-not-allowed'
              : 'border-red-500 text-red-500 hover:bg-red-50'
          }`}
          title={validated ? MATCH_DETAIL_UNVALIDATE_FIRST : undefined}
        >
          {MATCH_REJECT}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded hover:bg-gray-100"
        >
          {MODAL_CLOSE}
        </button>
      </div>
    </div>
  );
}
