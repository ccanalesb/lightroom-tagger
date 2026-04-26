import type { Match } from '../../../services/api';
import { ConfirmModalFrame } from '../../ui/ConfirmUndoAction';
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
    <ConfirmModalFrame
      title={<span className="text-red-600">{MATCH_REJECT_TITLE}</span>}
      confirmLabel={MATCH_REJECT_CONFIRM}
      cancelLabel={MATCH_REJECT_CANCEL}
      onConfirm={onConfirm}
      onCancel={onCancel}
      busy={busy}
      confirmVariant="danger"
    >
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
    </ConfirmModalFrame>
  );
}
