import {
  MATCH_DETAIL_VISION_LABEL,
  MATCH_DETAIL_SCORE_LABEL,
  MATCH_DETAIL_PHASH_LABEL,
} from '../../../constants/strings';
import type { Match } from '../../../services/api';
import { visionBadgeClasses } from '../../../utils/visionBadge';

interface MatchScoreBadgesProps {
  match: Match;
}

/**
 * Row of score/vision badges shown at the top of the match modal
 * body. Pure display — no state of its own.
 */
export function MatchScoreBadges({ match }: MatchScoreBadgesProps) {
  const visionResult = match.vision_result || 'UNCERTAIN';
  return (
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
  );
}
