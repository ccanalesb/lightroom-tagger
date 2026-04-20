import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { TileGrid } from '../ui/TileGrid';
import {
  TAB_MATCHES,
  MATCHES_TAB_EMPTY,
  MATCHES_VALIDATED_DIVIDER_LABEL,
  ITEMS_PER_PAGE,
  FILTER_LABEL_SORT_DATE,
  FILTER_SORT_DATE_NEWEST,
  FILTER_SORT_DATE_OLDEST,
  msgShowingOf,
} from '../../constants/strings';
import { SkeletonGrid } from '../ui/page-states';
import { useMatchGroups } from '../../hooks/useMatchGroups';
import { MatchDetailModal } from '../matching/match-detail-modal/MatchDetailModal';
import type { Match, MatchGroup } from '../../services/api';
import { MatchGroupTile } from './MatchGroupTile';
import { FilterBar } from '../filters/FilterBar';
import { useFilters } from '../../hooks/useFilters';
import type { FilterSchema } from '../filters/types';

export function MatchesTab() {
  const { matchGroups, total, fetchGroups, handleValidationChange, handleRejected } = useMatchGroups();
  const [loading, setLoading] = useState(true);
  const [selectedGroup, setSelectedGroup] = useState<MatchGroup | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);

  const matchesSchema = useMemo<FilterSchema>(
    () => [
      {
        type: 'select',
        key: 'sortByDate',
        label: FILTER_LABEL_SORT_DATE,
        paramName: 'sort_by_date',
        defaultValue: 'newest',
        options: [
          { value: 'newest', label: FILTER_SORT_DATE_NEWEST },
          { value: 'oldest', label: FILTER_SORT_DATE_OLDEST },
        ],
      },
    ],
    [],
  );
  const filters = useFilters(matchesSchema);
  const { values: filterValues } = filters;
  const sortByDate = filterValues.sortByDate as string | undefined;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = { sort_by_date: (sortByDate ?? 'newest') as 'newest' | 'oldest' };
    void fetchGroups(100, 0, params).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchGroups, sortByDate]);

  const openReview = useCallback((group: MatchGroup, candidate: Match) => {
    setSelectedGroup(group);
    setSelectedMatch(candidate);
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

  // Hide groups with no live candidates (all rejected / tombstones).
  const visibleGroups = matchGroups.filter(
    (g) => !g.all_rejected && g.candidates.length > 0,
  );
  const unvalidatedGroups = visibleGroups.filter((g) => !g.has_validated);
  const reviewedGroups = visibleGroups.filter((g) => g.has_validated);
  const showValidatedDivider = unvalidatedGroups.length > 0 && reviewedGroups.length > 0;

  const loadMoreParams = {
    sort_by_date: (sortByDate ?? 'newest') as 'newest' | 'oldest',
  };

  return (
    <div className="space-y-6">
      <h2 className="text-card-title text-text">{TAB_MATCHES}</h2>
      <FilterBar
        schema={matchesSchema}
        filters={filters}
        summary={
          <p className="text-sm text-text-secondary">
            {msgShowingOf(matchGroups.length, total, 'groups')}
          </p>
        }
        disabled={loading}
      />

      {loading ? (
        <SkeletonGrid count={ITEMS_PER_PAGE} />
      ) : visibleGroups.length === 0 ? (
        <Card padding="lg">
          <CardContent>
            <p className="text-sm text-text-secondary text-center py-8">{MATCHES_TAB_EMPTY}</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <TileGrid>
            {unvalidatedGroups.map((group) => (
              <MatchGroupTile key={group.instagram_key} group={group} onOpenReview={openReview} />
            ))}
          </TileGrid>
          {showValidatedDivider ? (
            <div
              className="w-full border-t border-border pt-4 text-center text-xs text-text-secondary"
              role="separator"
            >
              {MATCHES_VALIDATED_DIVIDER_LABEL}
            </div>
          ) : null}
          {reviewedGroups.length > 0 ? (
            <TileGrid>
              {reviewedGroups.map((group) => (
                <MatchGroupTile key={group.instagram_key} group={group} onOpenReview={openReview} />
              ))}
            </TileGrid>
          ) : null}
          {matchGroups.length < total ? (
            <div className="flex justify-center pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => fetchGroups(50, matchGroups.length, loadMoreParams)}
              >
                Load more
              </Button>
            </div>
          ) : null}
        </>
      )}

      {liveGroup && liveGroup.candidates.length > 0 && liveMatch ? (
        <MatchDetailModal
          match={liveMatch}
          group={() =>
            matchGroups.find((g) => g.instagram_key === liveGroup.instagram_key) ?? liveGroup
          }
          onClose={closeModal}
          onValidationChange={(m, validated) => {
            handleValidationChange(m, validated);
            if (validated) closeModal();
          }}
          onRejected={handleRejected}
          onCandidateChange={setSelectedMatch}
        />
      ) : null}
    </div>
  );
}
