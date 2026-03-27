import { useState } from 'react';
import type { Match } from '../../services/api';
import { MATCH_DETAIL_INSTAGRAM, MATCH_DETAIL_CATALOG } from '../../constants/strings';

interface MatchImagesSectionProps {
  match: Match;
}

export function MatchImagesSection({ match }: MatchImagesSectionProps) {
  const [instaLoaded, setInstaLoaded] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);

  const instaUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}/thumbnail`;
  const catalogUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}/thumbnail`;

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">{MATCH_DETAIL_INSTAGRAM}</h4>
        <div className="relative bg-gray-100 rounded-lg overflow-hidden aspect-square">
          {!instaLoaded && (
            <div className="absolute inset-0 bg-gray-200 animate-pulse" />
          )}
          <img
            src={instaUrl}
            alt={MATCH_DETAIL_INSTAGRAM}
            className={`w-full h-full object-contain transition-opacity duration-300 ${
              instaLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            onLoad={() => setInstaLoaded(true)}
          />
        </div>
        <p className="text-xs text-gray-500 break-all">
          {match.instagram_image?.filename || match.instagram_key}
        </p>
        {match.instagram_image?.description && (
          <p className="text-xs text-gray-600 line-clamp-3">
            {match.instagram_image.description}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">{MATCH_DETAIL_CATALOG}</h4>
        <div className="relative bg-gray-100 rounded-lg overflow-hidden aspect-square">
          {!catalogLoaded && (
            <div className="absolute inset-0 bg-gray-200 animate-pulse" />
          )}
          <img
            src={catalogUrl}
            alt={MATCH_DETAIL_CATALOG}
            className={`w-full h-full object-contain transition-opacity duration-300 ${
              catalogLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            onLoad={() => setCatalogLoaded(true)}
          />
        </div>
        <p className="text-xs text-gray-500 break-all">
          {match.catalog_image?.filename || match.catalog_key}
        </p>
        {match.catalog_image?.caption && (
          <p className="text-xs text-gray-600 line-clamp-3">
            {match.catalog_image.caption}
          </p>
        )}
      </div>
    </div>
  );
}
