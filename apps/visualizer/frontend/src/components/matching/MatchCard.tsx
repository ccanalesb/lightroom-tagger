import { useEffect, useState } from 'react';
import type { Match, MatchGroup } from '../../services/api';
import {
  MATCH_CARD_IG_LABEL,
  MATCH_CARD_CATALOG_LABEL,
  MATCH_CARD_NO_IMAGE,
  MATCH_VALIDATED,
  LABEL_MODEL,
} from '../../constants/strings';
import { PerspectiveBadge } from './PerspectiveBadge';
import { VisionBadge } from '../ui/badges';
import { Thumbnail } from '../ui/Thumbnail';
import { ScoreTooltip } from './ScoreTooltip';
import { CandidateCarousel } from './CandidateCarousel';
import { thumbnailUrl } from '../../utils/imageUrl';

interface MatchCardProps {
  group: MatchGroup;
  onClick?: (candidate: Match) => void;
}

export function MatchCard({ group, onClick }: MatchCardProps) {
  const [candidateIdx, setCandidateIdx] = useState(0);
  const [instaLoaded, setInstaLoaded] = useState(false);
  const [instaError, setInstaError] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const candidate = group.candidates[candidateIdx];
  const instaSrc = thumbnailUrl('instagram', group.instagram_key);
  const getFilename = (key: string) => key.split('_').pop() || key;

  useEffect(() => {
    setCandidateIdx((idx) => {
      const last = Math.max(0, group.candidates.length - 1);
      return Math.min(idx, last);
    });
  }, [group.candidates.length, group.instagram_key]);

  if (!candidate) {
    return null;
  }

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white cursor-pointer"
      onClick={() => onClick?.(candidate)}
    >
      <div className="flex h-32">
        <Thumbnail
          url={instaSrc}
          label={MATCH_CARD_IG_LABEL}
          loaded={instaLoaded}
          error={instaError}
          onLoad={() => setInstaLoaded(true)}
          onError={() => setInstaError(true)}
          errorText={MATCH_CARD_NO_IMAGE}
        />
        <CandidateCarousel
          catalogKeys={group.candidates.map((c) => c.catalog_key)}
          activeIndex={candidateIdx}
          onIndexChange={setCandidateIdx}
        />
      </div>

      <div className="p-3">
        <div className="flex justify-between items-start mb-2">
          <div className="flex gap-1">
            <VisionBadge result={candidate.vision_result} />
            {candidate.validated_at && (
              <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-600 text-white">
                &#x2713; {MATCH_VALIDATED}
              </span>
            )}
          </div>
          <ScoreTooltip match={candidate} show={showTooltip}>
            <span
              className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 cursor-help"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              {(candidate.score * 100).toFixed(0)}%
            </span>
          </ScoreTooltip>
        </div>

        <div className="text-xs space-y-1">
          <p className="text-gray-900 truncate" title={group.instagram_image?.filename || group.instagram_key}>
            {MATCH_CARD_IG_LABEL}: {group.instagram_image?.filename || getFilename(group.instagram_key)}
          </p>
          <p className="text-gray-600 truncate" title={candidate.catalog_image?.filename || candidate.catalog_key}>
            {MATCH_CARD_CATALOG_LABEL}: {candidate.catalog_image?.filename || getFilename(candidate.catalog_key)}
          </p>
          <PerspectiveBadge match={candidate} />
          {candidate.model_used && (
            <p className="text-gray-400 truncate" title={candidate.model_used}>
              {LABEL_MODEL} {candidate.model_used}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
