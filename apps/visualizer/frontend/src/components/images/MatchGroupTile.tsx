import { Badge } from '../ui/badges';
import { ImageTile, fromMatchSide } from '../image-view';
import { MATCH_VALIDATED, msgMatchGroupCandidates } from '../../constants/strings';
import type { Match, MatchGroup } from '../../services/api';
import { pickInitialMatch } from './pickInitialMatch';

interface MatchGroupTileProps {
  group: MatchGroup;
  onOpenReview: (group: MatchGroup, candidate: Match) => void;
}

/**
 * List tile for a match group: Instagram thumbnail with footer metadata.
 * Validated groups show the catalog filename; unvalidated groups show only candidate count.
 */
export function MatchGroupTile({ group, onOpenReview }: MatchGroupTileProps) {
  const initial = pickInitialMatch(group);
  if (!initial) return null;
  const instagramView = fromMatchSide(
    { ...initial, instagram_image: group.instagram_image },
    'instagram',
  );

  const footer = group.has_validated ? (
    <div className="flex flex-wrap items-center gap-2 justify-between">
      <div className="flex items-center gap-2">
        <Badge variant="success">{MATCH_VALIDATED}</Badge>
        {typeof group.best_score === 'number' && (
          <Badge variant="default">{Math.round(group.best_score * 100)}%</Badge>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="w-full truncate text-xs text-text-secondary">
          {initial.catalog_image?.filename ?? initial.catalog_key}
        </p>
      </div>
    </div>
  ) : (
    <p className="text-xs text-text-secondary">
      {msgMatchGroupCandidates(group.candidate_count)}
    </p>
  );

  return (
    <ImageTile
      image={instagramView}
      variant="grid"
      primaryScoreSource="none"
      footer={footer}
      onClick={() => onOpenReview(group, initial)}
    />
  );
}
