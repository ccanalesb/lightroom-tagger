import { Badge } from '../ui/badges';
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
  return (
    <ImageTile
      image={instagramView}
      variant="grid"
      primaryScoreSource="none"
      overlayBadges={renderOverlayBadge(group)}
      onClick={() => onOpenReview(group, initial)}
    />
  );
}

/**
 * Decide which overlay badge the group tile should show:
 *   - "Validated" (success) when the group already has a validated match.
 *   - "N candidate(s)" (accent) otherwise.
 */
function renderOverlayBadge(group: MatchGroup) {
  if (group.has_validated) {
    return <Badge variant="success">{MATCH_VALIDATED}</Badge>;
  }
  const count = group.candidate_count;
  return (
    <Badge variant="accent">
      {count} candidate{count === 1 ? '' : 's'}
    </Badge>
  );
}
