import { useState } from 'react';
import { MODAL_CLOSE, MATCHING_RESULTS } from '../constants/strings';
import type { Match } from '../services/api';

interface MatchDetailModalProps {
  match: Match;
  onClose: () => void;
}

export function MatchDetailModal({ match, onClose }: MatchDetailModalProps) {
  const [instaLoaded, setInstaLoaded] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);

  const instaUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}`;
  const catalogUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}`;

  const visionResult = match.vision_result || 'UNCERTAIN';
  const visionBadgeColors: Record<string, string> = {
    SAME: 'bg-green-100 text-green-800',
    DIFFERENT: 'bg-red-100 text-red-800',
    UNCERTAIN: 'bg-yellow-100 text-yellow-800',
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-bold text-gray-900">{MATCHING_RESULTS}</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded hover:bg-gray-100"
          >
            {MODAL_CLOSE}
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Score and result badges */}
          <div className="flex gap-2 flex-wrap">
            <span
              className={`inline-flex items-center px-3 py-1 rounded text-sm font-medium ${
                visionBadgeColors[visionResult] || visionBadgeColors.UNCERTAIN
              }`}
            >
              Vision: {visionResult}
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-blue-100 text-blue-800">
              Score: {(match.score * 100).toFixed(0)}%
            </span>
            {match.phash_score !== undefined && (
              <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-gray-100 text-gray-700">
                PHash: {(match.phash_score * 100).toFixed(0)}%
              </span>
            )}
            {match.vision_score !== undefined && (
              <span className="inline-flex items-center px-3 py-1 rounded text-sm font-medium bg-purple-100 text-purple-800">
                Vision: {(match.vision_score * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {/* Images side by side */}
          <div className="grid grid-cols-2 gap-4">
            {/* Instagram image */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-gray-700">Instagram</h4>
              <div className="relative bg-gray-100 rounded-lg overflow-hidden aspect-square">
                {!instaLoaded && (
                  <div className="absolute inset-0 bg-gray-200 animate-pulse" />
                )}
                <img
                  src={instaUrl}
                  alt="Instagram"
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

            {/* Catalog image */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-gray-700">Catalog</h4>
              <div className="relative bg-gray-100 rounded-lg overflow-hidden aspect-square">
                {!catalogLoaded && (
                  <div className="absolute inset-0 bg-gray-200 animate-pulse" />
                )}
                <img
                  src={catalogUrl}
                  alt="Catalog"
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

          {/* Metadata */}
          <div className="bg-gray-50 p-4 rounded-lg text-sm space-y-2">
            <h4 className="font-medium text-gray-700">Match Details</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-gray-500">Instagram Key:</span>
                <p className="font-mono text-xs break-all">{match.instagram_key}</p>
              </div>
              <div>
                <span className="text-gray-500">Catalog Key:</span>
                <p className="font-mono text-xs break-all">{match.catalog_key}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
