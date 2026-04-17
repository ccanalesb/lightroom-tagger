import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  TAB_MATCHES,
  MATCH_VALIDATED,
  MATCHES_TAB_EMPTY,
  MSG_LOADING,
  MATCHES_VALIDATED_DIVIDER_LABEL,
  MATCH_TOMBSTONE_NO_MATCH_BADGE,
  MATCH_TOMBSTONE_CARD_ARIA_LABEL,
} from '../../constants/strings';
import { useMatchGroups } from '../../hooks/useMatchGroups';
import { MatchDetailModal } from '../matching/match-detail-modal/MatchDetailModal';
import type { Match, MatchGroup } from '../../services/api';

function pickInitialMatch(group: MatchGroup): Match | undefined {
  if (group.candidates.length === 0) return undefined;
  const rank1 = group.candidates.find((c) => c.rank === 1);
  if (rank1) return rank1;
  return group.candidates.reduce((best, c) => (c.score > best.score ? c : best));
}

function ActionableMatchGroupCard({
  group,
  onOpenReview,
}: {
  group: MatchGroup;
  onOpenReview: (group: MatchGroup) => void;
}) {
  return (
    <Card padding="md">
      <CardContent>
        <div className="flex flex-col sm:flex-row gap-4 sm:items-center">
          <div className="aspect-square w-full max-w-[120px] shrink-0 bg-surface rounded-base overflow-hidden mx-auto sm:mx-0">
            <img
              src={`/api/images/instagram/${encodeURIComponent(group.instagram_key)}/thumbnail`}
              alt=""
              className="w-full h-full object-contain"
            />
          </div>
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-text break-all">{group.instagram_key}</span>
              {group.has_validated ? <Badge variant="success">{MATCH_VALIDATED}</Badge> : null}
            </div>
            <p className="text-sm text-text-secondary">
              {group.candidate_count} candidate{group.candidate_count === 1 ? '' : 's'} · best score{' '}
              {group.best_score.toFixed(2)}
            </p>
            <Button type="button" variant="primary" size="sm" onClick={() => onOpenReview(group)}>
              Review
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TombstoneMatchGroupCard({ group }: { group: MatchGroup }) {
  return (
    <Card padding="md">
      <CardContent>
        <div
          className="flex flex-col sm:flex-row gap-4 sm:items-center"
          aria-label={MATCH_TOMBSTONE_CARD_ARIA_LABEL}
        >
          <div className="aspect-square w-full max-w-[120px] shrink-0 bg-surface rounded-base overflow-hidden mx-auto sm:mx-0">
            <img
              src={`/api/images/instagram/${encodeURIComponent(group.instagram_key)}/thumbnail`}
              alt=""
              className="w-full h-full object-contain"
            />
          </div>
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-text break-all">{group.instagram_key}</span>
              <Badge variant="error">{MATCH_TOMBSTONE_NO_MATCH_BADGE}</Badge>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ReviewedMatchGroupCard({
  group,
  onOpenReview,
}: {
  group: MatchGroup;
  onOpenReview: (group: MatchGroup) => void;
}) {
  const isTombstone = Boolean(group.all_rejected) || group.candidate_count === 0;
  if (isTombstone) {
    return <TombstoneMatchGroupCard group={group} />;
  }
  return <ActionableMatchGroupCard group={group} onOpenReview={onOpenReview} />;
}

export function MatchesTab() {
  const { matchGroups, total, fetchGroups, handleValidationChange, handleRejected } = useMatchGroups();
  const [loading, setLoading] = useState(true);
  const [selectedGroup, setSelectedGroup] = useState<MatchGroup | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchGroups(100, 0).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchGroups]);

  const openReview = useCallback((group: MatchGroup) => {
    setSelectedGroup(group);
    setSelectedMatch(pickInitialMatch(group) ?? null);
  }, []);

  const closeModal = useCallback(() => {
    setSelectedGroup(null);
    setSelectedMatch(null);
  }, []);

  const liveGroup =
    selectedGroup &&
    (matchGroups.find((g) => g.instagram_key === selectedGroup.instagram_key) ?? selectedGroup);
  const liveMatch =
    liveGroup && selectedMatch && liveGroup.candidates.length > 0
      ? liveGroup.candidates.find(
          (c) =>
            c.catalog_key === selectedMatch.catalog_key &&
            c.instagram_key === selectedMatch.instagram_key,
        ) ?? null
      : null;

  const unvalidatedGroups = matchGroups.filter((g) => !g.has_validated && !g.all_rejected);
  const reviewedGroups = matchGroups.filter((g) => g.has_validated || Boolean(g.all_rejected));
  const showValidatedDivider = unvalidatedGroups.length > 0 && reviewedGroups.length > 0;

  return (
    <div className="space-y-6">
      <h2 className="text-card-title text-text">{TAB_MATCHES}</h2>

      {loading ? (
        <Card padding="lg">
          <CardContent>
            <p className="text-sm text-text-secondary text-center py-8">{MSG_LOADING}</p>
          </CardContent>
        </Card>
      ) : matchGroups.length === 0 ? (
        <Card padding="lg">
          <CardContent>
            <p className="text-sm text-text-secondary text-center py-8">{MATCHES_TAB_EMPTY}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {unvalidatedGroups.map((group) => (
            <ActionableMatchGroupCard key={group.instagram_key} group={group} onOpenReview={openReview} />
          ))}
          {showValidatedDivider ? (
            <div
              className="w-full border-t border-border pt-4 text-center text-xs text-text-secondary"
              role="separator"
            >
              {MATCHES_VALIDATED_DIVIDER_LABEL}
            </div>
          ) : null}
          {reviewedGroups.map((group) => (
            <ReviewedMatchGroupCard key={group.instagram_key} group={group} onOpenReview={openReview} />
          ))}
          {matchGroups.length < total ? (
            <div className="flex justify-center pt-2">
              <Button type="button" variant="secondary" onClick={() => fetchGroups(50, matchGroups.length)}>
                Load more
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {liveGroup && liveGroup.candidates.length > 0 && liveMatch ? (
        <MatchDetailModal
          match={liveMatch}
          group={() =>
            matchGroups.find((g) => g.instagram_key === liveGroup.instagram_key) ?? liveGroup
          }
          onClose={closeModal}
          onValidationChange={handleValidationChange}
          onRejected={handleRejected}
          onCandidateChange={setSelectedMatch}
        />
      ) : null}
    </div>
  );
}
