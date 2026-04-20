import { Badge } from '../ui/Badge';
import { ImageTile, fromMatchSide } from '../image-view';
import { MATCH_VALIDATED } from '../../constants/strings';
import type { Match, MatchGroup } from '../../services/api';
import { pickInitialMatch } from './pickInitialMatch';

interface MatchGroupTileProps {
  group: MatchGroup;
  onOpenReview: (group: MatchGroup, candidate: Match) => void;
}

/**
 * List tile for a match group: renders the Instagram image only,
 * with an overlay badge indicating validation state or the number
 * of candidates. Clicking opens the match review modal.
 */
export function MatchGroupTile({ group, onOpenReview }: MatchGroupTileProps) {
  const initial = pickInitialMatch(group);
  if (!initial) return null;
  const instagramView = fromMatchSide(
    { ...initial, instagram_image: group.instagram_image },
    'instagram',
  );
  const count = group.candidate_count;
  return (
    <ImageTile
      image={instagramView}
      variant="grid"
      primaryScoreSource="none"
      overlayBadges={
        group.has_validated ? (
          <Badge variant="success">{MATCH_VALIDATED}</Badge>
        ) : (
          <Badge variant="accent">
            {count} candidate{count === 1 ? '' : 's'}
          </Badge>
        )
      }
      onClick={() => onOpenReview(group, initial)}
    />
  );
}
