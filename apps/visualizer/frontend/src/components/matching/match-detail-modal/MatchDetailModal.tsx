import { useEffect, useState } from 'react';
import {
  MODAL_CLOSE,
  MATCHING_RESULTS,
  MATCH_DETAIL_VISION_LABEL,
  MATCH_DETAIL_SCORE_LABEL,
  MATCH_DETAIL_PHASH_LABEL,
  MATCH_VALIDATE,
  MATCH_VALIDATED,
  MATCH_REJECT,
  MATCH_DETAIL_UNVALIDATE_FIRST,
} from '../../../constants/strings';
import type { Match } from '../../../services/api';
import { MatchingAPI } from '../../../services/api';
import { MatchImagesSection } from './MatchImagesSection';
import { MatchDescriptionsSection } from './MatchDescriptionsSection';
import { MatchMetadataSection } from './MatchMetadataSection';
import { RejectConfirmModal } from './RejectConfirmModal';
import { visionBadgeClasses } from '../../../utils/visionBadge';

interface MatchDetailModalProps {
  match: Match;
  onClose: () => void;
  onValidationChange?: (match: Match, validated: boolean) => void;
  onRejected?: (match: Match) => void;
}

export function MatchDetailModal({ match, onClose, onValidationChange, onRejected }: MatchDetailModalProps) {
  const visionResult = match.vision_result || 'UNCERTAIN';
  const [validated, setValidated] = useState(!!match.validated_at);
  const [busy, setBusy] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);

  useEffect(() => {
    setValidated(!!match.validated_at);
  }, [match.validated_at]);

  async function handleValidate() {
    setBusy(true);
    try {
      const res = await MatchingAPI.validate(match.catalog_key, match.instagram_key);
      setValidated(res.validated);
      onValidationChange?.(match, res.validated);
    } finally {
      setBusy(false);
    }
  }

  async function handleRejectConfirm() {
    setBusy(true);
    try {
      await MatchingAPI.reject(match.catalog_key, match.instagram_key);
      onRejected?.(match);
      onClose();
    } finally {
      setBusy(false);
      setShowRejectModal(false);
    }
  }

  const instaThumbnailUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}/thumbnail`;
  const catalogThumbnailUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}/thumbnail`;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        onClick={onClose}
      >
        <div
          className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex justify-between items-center p-4 border-b">
            <h3 className="text-lg font-bold text-gray-900">{MATCHING_RESULTS}</h3>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleValidate}
                disabled={busy}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  validated
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'border border-green-600 text-green-600 hover:bg-green-50'
                }`}
              >
                {validated ? `\u2713 ${MATCH_VALIDATED}` : MATCH_VALIDATE}
              </button>
              <button
                type="button"
                onClick={() => setShowRejectModal(true)}
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

          <div className="p-4 space-y-4">
            <div className="flex gap-2 flex-wrap">
              <span
                className={`inline-flex items-center px-3 py-1 rounded text-sm font-medium ${visionBadgeClasses(match.vision_result)}`}
              >
                {MATCH_DETAIL_VISION_LABEL} {visionResult}
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-blue-100 text-blue-800">
                {MATCH_DETAIL_SCORE_LABEL} {(match.score * 100).toFixed(0)}%
              </span>
              {match.phash_score !== undefined && (
                <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-gray-100 text-gray-700">
                  {MATCH_DETAIL_PHASH_LABEL} {(match.phash_score * 100).toFixed(0)}%
                </span>
              )}
              {match.vision_score !== undefined && (
                <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-purple-100 text-purple-800">
                  {MATCH_DETAIL_VISION_LABEL} {(match.vision_score * 100).toFixed(0)}%
                </span>
              )}
            </div>

            <MatchImagesSection match={match} />
            <MatchDescriptionsSection match={match} />
            <MatchMetadataSection match={match} />
          </div>
        </div>
      </div>

      {showRejectModal && (
        <RejectConfirmModal
          match={match}
          instaThumbnailUrl={instaThumbnailUrl}
          catalogThumbnailUrl={catalogThumbnailUrl}
          busy={busy}
          onConfirm={handleRejectConfirm}
          onCancel={() => setShowRejectModal(false)}
        />
      )}
    </>
  );
}
