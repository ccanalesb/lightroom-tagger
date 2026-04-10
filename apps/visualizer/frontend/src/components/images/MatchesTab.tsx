import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  TAB_MATCHES,
  MATCH_VALIDATED,
  MATCHES_TAB_EMPTY,
  MSG_LOADING,
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

export function MatchesTab() {
  const { matchGroups, fetchGroups, handleValidationChange, handleRejected } = useMatchGroups();
  const [loading, setLoading] = useState(true);
  const [selectedGroup, setSelectedGroup] = useState<MatchGroup | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetchGroups(100).finally(() => {
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
    liveGroup && selectedMatch
      ? liveGroup.candidates.find(
          (c) =>
            c.catalog_key === selectedMatch.catalog_key &&
            c.instagram_key === selectedMatch.instagram_key,
        ) ?? selectedMatch
      : selectedMatch;

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
          {matchGroups.map((group) => (
            <Card key={group.instagram_key} padding="md">
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
                      {group.has_validated ? (
                        <Badge variant="success">{MATCH_VALIDATED}</Badge>
                      ) : null}
                    </div>
                    <p className="text-sm text-text-secondary">
                      {group.candidate_count} candidate{group.candidate_count === 1 ? '' : 's'} · best
                      score {group.best_score.toFixed(2)}
                    </p>
                    <Button type="button" variant="primary" size="sm" onClick={() => openReview(group)}>
                      Review
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {liveGroup && liveMatch ? (
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
