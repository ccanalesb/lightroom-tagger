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
 * List tile for a match group: Instagram thumbnail with two stacked overlay
 * badges — validation/count badge and best-score pill — plus the catalog
 * filename in the footer when the group is validated.
 */
export function MatchGroupTile({ group, onOpenReview }: MatchGroupTileProps) {
  const initial = pickInitialMatch(group);
  if (!initial) return null;
  const instagramView = fromMatchSide(
    { ...initial, instagram_image: group.instagram_image },
    'instagram',
  );

  const footer = (
    <div className="flex flex-wrap items-center gap-2">
      {group.has_validated ? (
        <Badge variant="success">{MATCH_VALIDATED}</Badge>
      ) : (
        <Badge variant="accent">{msgMatchGroupCandidates(group.candidate_count)}</Badge>
      )}
      {typeof group.best_score === 'number' && (
        <Badge variant="default">{Math.round(group.best_score * 100)}%</Badge>
      )}
      {group.has_validated && (
        <p className="w-full truncate text-xs text-text-secondary">
          {initial.catalog_image?.filename ?? initial.catalog_key}
        </p>
      )}
    </div>
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
