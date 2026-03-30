import { useState } from 'react';
import type { Match } from '../../services/api';
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
import { thumbnailUrl } from '../../utils/imageUrl';

interface MatchCardProps {
  match: Match;
  onClick?: () => void;
}

export function MatchCard({ match, onClick }: MatchCardProps) {
  const [instaLoaded, setInstaLoaded] = useState(false);
  const [instaError, setInstaError] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const instaThumbnailUrl = thumbnailUrl('instagram', match.instagram_key);
  const catalogThumbnailUrl = thumbnailUrl('catalog', match.catalog_key);

  const getFilename = (key: string) => key.split('_').pop() || key;

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white cursor-pointer"
      onClick={onClick}
    >
      <div className="flex h-32">
        <Thumbnail
          url={instaThumbnailUrl}
          label={MATCH_CARD_IG_LABEL}
          loaded={instaLoaded}
          error={instaError}
          onLoad={() => setInstaLoaded(true)}
          onError={() => setInstaError(true)}
          errorText={MATCH_CARD_NO_IMAGE}
        />
        <Thumbnail
          url={catalogThumbnailUrl}
          label={MATCH_CARD_CATALOG_LABEL}
          loaded={catalogLoaded}
          error={catalogError}
          onLoad={() => setCatalogLoaded(true)}
          onError={() => setCatalogError(true)}
          alignRight
          errorText={MATCH_CARD_NO_IMAGE}
        />
      </div>

      <div className="p-3">
        <div className="flex justify-between items-start mb-2">
          <div className="flex gap-1">
            <VisionBadge result={match.vision_result} />
            {match.validated_at && (
              <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-600 text-white">
                &#x2713; {MATCH_VALIDATED}
              </span>
            )}
          </div>

          <ScoreTooltip match={match} show={showTooltip}>
            <span
              className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 cursor-help"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              {(match.score * 100).toFixed(0)}%
            </span>
          </ScoreTooltip>
        </div>

        <div className="text-xs space-y-1">
          <p className="text-gray-900 truncate" title={match.instagram_image?.filename || match.instagram_key}>
            {MATCH_CARD_IG_LABEL}: {match.instagram_image?.filename || getFilename(match.instagram_key)}
          </p>
          <p className="text-gray-600 truncate" title={match.catalog_image?.filename || match.catalog_key}>
            {MATCH_CARD_CATALOG_LABEL}: {match.catalog_image?.filename || getFilename(match.catalog_key)}
          </p>
          <PerspectiveBadge match={match} />
          {match.model_used && (
            <p className="text-gray-400 truncate" title={match.model_used}>
              {LABEL_MODEL} {match.model_used}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
