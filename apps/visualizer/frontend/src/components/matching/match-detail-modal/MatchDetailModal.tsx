import { useEffect, useRef, useState } from 'react';
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
  MATCH_DETAIL_REJECTED_LABEL,
  MATCH_DETAIL_REJECTED_AUTOCLOSE_MS,
} from '../../../constants/strings';
import type { Match, MatchGroup } from '../../../services/api';
import { MatchingAPI } from '../../../services/api';
import { Badge } from '../../ui/Badge';
import { CandidateTabBar } from './CandidateTabBar';
import { MatchImagesSection } from './MatchImagesSection';
import { MatchDescriptionsSection } from './MatchDescriptionsSection';
import { MatchMetadataSection } from './MatchMetadataSection';
import { RejectConfirmModal } from './RejectConfirmModal';
import { VisionReasoningNote } from './VisionReasoningNote';
import { visionBadgeClasses } from '../../../utils/visionBadge';

/** Delay before switching tabs after reject when another candidate exists (modal stays open). */
export const MULTI_CANDIDATE_REJECT_ADVANCE_MS = 800;

function findNextCandidateInOrder(candidates: Match[], current: Match): Match | undefined {
  const idx = candidates.findIndex(
    (c) => c.catalog_key === current.catalog_key && c.instagram_key === current.instagram_key,
  );
  if (idx === -1 || idx >= candidates.length - 1) return undefined;
  return candidates[idx + 1];
}

interface MatchDetailModalProps {
  match: Match;
  group?: MatchGroup | (() => MatchGroup | undefined);
  onClose: () => void;
  onValidationChange?: (match: Match, validated: boolean) => void;
  onRejected?: (match: Match) => void;
  onCandidateChange?: (candidate: Match) => void;
}

export function MatchDetailModal({
  match,
  group,
  onClose,
  onValidationChange,
  onRejected,
  onCandidateChange,
}: MatchDetailModalProps) {
  const resolvedGroup = typeof group === 'function' ? group() : group;
  const visionResult = match.vision_result || 'UNCERTAIN';
  const [validated, setValidated] = useState(!!match.validated_at);
  const [busy, setBusy] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectedAck, setRejectedAck] = useState(false);
  const autoCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rejectAdvanceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearRejectFlowTimers() {
    if (autoCloseTimerRef.current !== null) {
      clearTimeout(autoCloseTimerRef.current);
      autoCloseTimerRef.current = null;
    }
    if (rejectAdvanceTimerRef.current !== null) {
      clearTimeout(rejectAdvanceTimerRef.current);
      rejectAdvanceTimerRef.current = null;
    }
  }

  useEffect(() => {
    setValidated(!!match.validated_at);
  }, [match.validated_at]);

  useEffect(() => {
    setRejectedAck(false);
    clearRejectFlowTimers();
    return () => {
      clearRejectFlowTimers();
    };
  }, [match.catalog_key, match.instagram_key]);

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
    const candidates = resolvedGroup?.candidates ?? [];
    const nextCandidate = findNextCandidateInOrder(candidates, match);

    setBusy(true);
    try {
      await MatchingAPI.reject(match.catalog_key, match.instagram_key);
      onRejected?.(match);
      clearRejectFlowTimers();

      if (nextCandidate && onCandidateChange) {
        setRejectedAck(true);
        rejectAdvanceTimerRef.current = window.setTimeout(() => {
          rejectAdvanceTimerRef.current = null;
          onCandidateChange(nextCandidate);
        }, MULTI_CANDIDATE_REJECT_ADVANCE_MS);
      } else {
        setRejectedAck(true);
        /* 1500ms — MATCH_DETAIL_REJECTED_AUTOCLOSE_MS (D-03 / D-05) */
        autoCloseTimerRef.current = window.setTimeout(() => {
          autoCloseTimerRef.current = null;
          onClose();
        }, MATCH_DETAIL_REJECTED_AUTOCLOSE_MS);
      }
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
          <div className="flex justify-between items-center p-4 border-b gap-3">
            <div className="flex items-center gap-2 min-w-0 flex-wrap">
              <h3 className="text-lg font-bold text-gray-900">{MATCHING_RESULTS}</h3>
              {rejectedAck ? (
                <Badge variant="error" className="shrink-0">
                  {MATCH_DETAIL_REJECTED_LABEL}
                </Badge>
              ) : null}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleValidate}
                disabled={busy || validated || rejectedAck}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  validated
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'border border-green-600 text-green-600 hover:bg-green-50'
                } ${busy || validated || rejectedAck ? 'opacity-60 cursor-not-allowed' : ''}`}
              >
                {validated ? `\u2713 ${MATCH_VALIDATED}` : MATCH_VALIDATE}
              </button>
              <button
                type="button"
                onClick={() => setShowRejectModal(true)}
                disabled={busy || validated || rejectedAck}
                className={`px-3 py-1 rounded text-sm font-medium border transition-colors ${
                  validated || rejectedAck
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

          {resolvedGroup && resolvedGroup.candidates.length > 1 && (
            <CandidateTabBar
              candidates={resolvedGroup.candidates}
              activeKey={match.catalog_key}
              onSelect={(c) => onCandidateChange?.(c)}
            />
          )}

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

            {match.vision_reasoning ? (
              <VisionReasoningNote visionReasoning={match.vision_reasoning} />
            ) : null}

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
