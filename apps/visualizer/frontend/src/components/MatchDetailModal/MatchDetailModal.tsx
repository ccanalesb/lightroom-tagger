import {
  MODAL_CLOSE,
  MATCHING_RESULTS,
  MATCH_DETAIL_VISION_LABEL,
  MATCH_DETAIL_SCORE_LABEL,
  MATCH_DETAIL_PHASH_LABEL,
} from '../../constants/strings';
import type { Match } from '../../services/api';
import { MatchImagesSection } from './MatchImagesSection';
import { MatchDescriptionsSection } from './MatchDescriptionsSection';
import { MatchMetadataSection } from './MatchMetadataSection';

const VISION_BADGE_COLORS: Record<string, string> = {
  SAME: 'bg-green-100 text-green-800',
  DIFFERENT: 'bg-red-100 text-red-800',
  UNCERTAIN: 'bg-yellow-100 text-yellow-800',
};

interface MatchDetailModalProps {
  match: Match;
  onClose: () => void;
}

export function MatchDetailModal({ match, onClose }: MatchDetailModalProps) {
  const visionResult = match.vision_result || 'UNCERTAIN';

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-bold text-gray-900">{MATCHING_RESULTS}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded hover:bg-gray-100"
          >
            {MODAL_CLOSE}
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="flex gap-2 flex-wrap">
            <span
              className={`inline-flex items-center px-3 py-1 rounded text-sm font-medium ${
                VISION_BADGE_COLORS[visionResult] || VISION_BADGE_COLORS.UNCERTAIN
              }`}
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

          <MatchImagesSection match={match} />
          <MatchDescriptionsSection match={match} />
          <MatchMetadataSection match={match} />
        </div>
      </div>
    </div>
  );
}
