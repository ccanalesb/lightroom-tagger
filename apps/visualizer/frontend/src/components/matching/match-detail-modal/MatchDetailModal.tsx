import { useEffect, useState } from 'react';
import { MATCHING_RESULTS } from '../../../constants/strings';
import type { Match, MatchGroup } from '../../../services/api';
import { MatchingAPI } from '../../../services/api';
import { MatchImagesSection } from './MatchImagesSection';
import { MatchDescriptionsSection } from './MatchDescriptionsSection';
import { MatchMetadataSection } from './MatchMetadataSection';
import { RejectConfirmModal } from './RejectConfirmModal';
import { VisionReasoningNote } from './VisionReasoningNote';
import { MatchDetailHeader } from './MatchDetailHeader';
import { MatchScoreBadges } from './MatchScoreBadges';
import { findNextCandidateInOrder } from './findNextCandidateInOrder';

interface MatchDetailModalProps {
  match: Match;
  group?: MatchGroup | (() => MatchGroup | undefined);
  onClose: () => void;
  onValidationChange?: (match: Match, validated: boolean) => void;
  onRejected?: (match: Match) => void;
  onCandidateChange?: (candidate: Match) => void;
}

/**
 * Match review modal. Stacked IG/candidate layout with carousel nav in
 * `MatchImagesSection`. Validate closes the modal immediately. Reject
 * auto-advances to the next candidate; if no candidates remain after
 * rejection, the modal closes.
 */
export function MatchDetailModal({
  match,
  group,
  onClose,
  onValidationChange,
  onRejected,
  onCandidateChange,
}: MatchDetailModalProps) {
  const resolvedGroup = typeof group === 'function' ? group() : group;
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
      // Close on validate (per UX contract). Unvalidate-then-something is
      // not supported from this modal anymore — user can re-open from list.
      if (res.validated) onClose();
    } finally {
      setBusy(false);
    }
  }

  async function handleRejectConfirm() {
    // Snapshot siblings *before* the reject mutates the group.
    const candidatesBefore = resolvedGroup?.candidates ?? [];
    const nextCandidate = findNextCandidateInOrder(candidatesBefore, match);

    setBusy(true);
    try {
      await MatchingAPI.reject(match.catalog_key, match.instagram_key);
      onRejected?.(match);

      if (nextCandidate && onCandidateChange) {
        onCandidateChange(nextCandidate);
      } else {
        onClose();
      }
    } finally {
      setBusy(false);
      setShowRejectModal(false);
    }
  }

  const instaThumbnailUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}/thumbnail`;
  const catalogThumbnailUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}/thumbnail`;

  const candidates = resolvedGroup?.candidates ?? [match];

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        onClick={onClose}
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label={MATCHING_RESULTS}
          className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <MatchDetailHeader
            validated={validated}
            busy={busy}
            onValidate={handleValidate}
            onReject={() => setShowRejectModal(true)}
            onClose={onClose}
          />

          <div className="p-4 space-y-4">
            <MatchScoreBadges match={match} />

            {match.vision_reasoning ? (
              <VisionReasoningNote visionReasoning={match.vision_reasoning} />
            ) : null}

            <MatchImagesSection
              candidates={candidates}
              activeMatch={match}
              onCandidateChange={(c) => onCandidateChange?.(c)}
            />
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
