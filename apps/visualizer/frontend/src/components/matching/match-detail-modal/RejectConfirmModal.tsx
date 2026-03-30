import type { Match } from '../../../services/api';
import {
  MATCH_CARD_IG_LABEL,
  MATCH_CARD_CATALOG_LABEL,
  MATCH_REJECT_TITLE,
  MATCH_REJECT_BODY,
  MATCH_REJECT_CANCEL,
  MATCH_REJECT_CONFIRM,
} from '../../../constants/strings';

interface RejectConfirmModalProps {
  match: Match;
  instaThumbnailUrl: string;
  catalogThumbnailUrl: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function RejectConfirmModal({ match, instaThumbnailUrl, catalogThumbnailUrl, busy, onConfirm, onCancel }: RejectConfirmModalProps) {
  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-[60] p-4"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-lg max-w-lg w-full shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b">
          <h3 className="text-lg font-bold text-red-600">{MATCH_REJECT_TITLE}</h3>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex gap-3 items-center">
            <div className="flex-1 text-center">
              <p className="text-xs text-gray-500 mb-1">{MATCH_CARD_IG_LABEL}</p>
              <img
                src={instaThumbnailUrl}
                alt="Instagram"
                className="w-full h-32 object-cover rounded border"
              />
              <p className="text-xs font-mono text-gray-600 mt-1 truncate" title={match.instagram_key}>
                {match.instagram_key}
              </p>
            </div>
            <div className="text-2xl text-gray-300">&ne;</div>
            <div className="flex-1 text-center">
              <p className="text-xs text-gray-500 mb-1">{MATCH_CARD_CATALOG_LABEL}</p>
              <img
                src={catalogThumbnailUrl}
                alt="Catalog"
                className="w-full h-32 object-cover rounded border"
              />
              <p className="text-xs font-mono text-gray-600 mt-1 truncate" title={match.catalog_key}>
                {match.catalog_key}
              </p>
            </div>
          </div>

          <p className="text-sm text-gray-600">{MATCH_REJECT_BODY}</p>
        </div>

        <div className="flex justify-end gap-2 p-4 border-t bg-gray-50 rounded-b-lg">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="px-4 py-2 rounded text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
          >
            {MATCH_REJECT_CANCEL}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="px-4 py-2 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
          >
            {busy ? '...' : MATCH_REJECT_CONFIRM}
          </button>
        </div>
      </div>
    </div>
  );
}
