import {
  MATCH_DETAIL_VISION_LABEL,
  MATCH_DETAIL_VISION_SCORE_LABEL,
  MATCH_DETAIL_DESC_LABEL,
  MATCH_DETAIL_SCORE_LABEL,
  MATCH_DETAIL_PHASH_LABEL,
} from '../../../constants/strings';
import type { Match } from '../../../services/api';
import { visionBadgeClasses } from '../../../utils/visionBadge';

interface MatchScoreBadgesProps {
  match: Match;
}

/**
 * Vision was genuinely used if it produced a real verdict (SAME/DIFFERENT)
 * or if the vision score is non-zero. An UNCERTAIN result with score=0 means
 * vision was skipped (vision_weight=0 or batch-path fallback).
 */
function visionWasUsed(match: Match): boolean {
  if (match.vision_result === 'SAME' || match.vision_result === 'DIFFERENT') return true;
  if (match.vision_score !== undefined && match.vision_score > 0) return true;
  return false;
}

/**
 * Row of score badges shown at the top of the match modal body.
 * Only shows signals that were actually used in scoring.
 */
export function MatchScoreBadges({ match }: MatchScoreBadgesProps) {
  const showVision = visionWasUsed(match);

  return (
    <div className="flex gap-2 flex-wrap">
      {/* Overall score — always shown */}
      <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-blue-100 text-blue-800">
        {MATCH_DETAIL_SCORE_LABEL} {(match.score * 100).toFixed(0)}%
      </span>

      {/* pHash perceptual hash similarity */}
      {match.phash_score !== undefined && (
        <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-gray-100 text-gray-700">
          {MATCH_DETAIL_PHASH_LABEL} {(match.phash_score * 100).toFixed(0)}%
        </span>
      )}

      {/* Description (AI text) similarity — only when a score was produced */}
      {match.desc_similarity !== undefined && match.desc_similarity > 0 && (
        <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-amber-100 text-amber-800">
          {MATCH_DETAIL_DESC_LABEL} {(match.desc_similarity * 100).toFixed(0)}%
        </span>
      )}

      {/* Vision verdict badge — only when vision was actually run */}
      {showVision && (
        <span
          className={`inline-flex items-center px-3 py-1 rounded text-sm font-medium ${visionBadgeClasses(match.vision_result)}`}
        >
          {MATCH_DETAIL_VISION_LABEL} {match.vision_result}
        </span>
      )}

      {/* Vision numeric score — only when vision was actually run */}
      {showVision && match.vision_score !== undefined && (
        <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-purple-100 text-purple-800">
          {MATCH_DETAIL_VISION_SCORE_LABEL} {(match.vision_score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
}
