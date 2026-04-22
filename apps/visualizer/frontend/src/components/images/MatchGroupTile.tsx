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
 * List tile for a match group: Instagram thumbnail with Catalog-style card
 * shell; validation state and catalog filename (when validated) or candidate
 * count (when not) appear in the footer metadata row — not on the thumbnail.
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
      <p className="text-xs text-text-secondary truncate max-w-full">
        {initial.catalog_image?.filename ?? initial.catalog_key}
      </p>
      <Badge variant="success">{MATCH_VALIDATED}</Badge>
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
