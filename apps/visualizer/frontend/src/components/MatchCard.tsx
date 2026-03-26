import { useState } from 'react';
import type { Match } from '../services/api';
import {
  MATCH_CARD_IG_LABEL,
  MATCH_CARD_CATALOG_LABEL,
  MATCH_CARD_NO_IMAGE,
  DESC_BEST_FIT,
  DESC_PERSPECTIVE_STREET,
  DESC_PERSPECTIVE_DOCUMENTARY,
  DESC_PERSPECTIVE_PUBLISHER,
} from '../constants/strings';

const PERSPECTIVE_BADGE_LABELS: Record<string, string> = {
  street: DESC_PERSPECTIVE_STREET,
  documentary: DESC_PERSPECTIVE_DOCUMENTARY,
  publisher: DESC_PERSPECTIVE_PUBLISHER,
};

function perspectiveBadgeColor(score: number): string {
  if (score >= 7) return 'bg-green-50 text-green-700';
  if (score >= 5) return 'bg-yellow-50 text-yellow-700';
  return 'bg-red-50 text-red-700';
}

interface MatchCardProps {
  match: Match;
  onClick?: () => void;
}

const VISION_BADGE_COLORS: Record<string, string> = {
  SAME: 'bg-green-100 text-green-800',
  DIFFERENT: 'bg-red-100 text-red-800',
  UNCERTAIN: 'bg-yellow-100 text-yellow-800',
};

export function MatchCard({ match, onClick }: MatchCardProps) {
  const [instaLoaded, setInstaLoaded] = useState(false);
  const [instaError, setInstaError] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const visionResult = match.vision_result || 'UNCERTAIN';
  const visionBadgeColor = VISION_BADGE_COLORS[visionResult] || VISION_BADGE_COLORS.UNCERTAIN;

  const instaThumbnailUrl = `/api/images/instagram/${encodeURIComponent(match.instagram_key)}/thumbnail`;
  const catalogThumbnailUrl = `/api/images/catalog/${encodeURIComponent(match.catalog_key)}/thumbnail`;

  const getFilename = (key: string) => key.split('_').pop() || key;

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow bg-white cursor-pointer"
      onClick={onClick}
    >
      {/* Thumbnails side by side */}
      <div className="flex h-32">
        <Thumbnail
          url={instaThumbnailUrl}
          label={MATCH_CARD_IG_LABEL}
          loaded={instaLoaded}
          error={instaError}
          onLoad={() => setInstaLoaded(true)}
          onError={() => setInstaError(true)}
        />
        <Thumbnail
          url={catalogThumbnailUrl}
          label={MATCH_CARD_CATALOG_LABEL}
          loaded={catalogLoaded}
          error={catalogError}
          onLoad={() => setCatalogLoaded(true)}
          onError={() => setCatalogError(true)}
          alignRight
        />
      </div>

      {/* Details */}
      <div className="p-3">
        <div className="flex justify-between items-start mb-2">
          <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${visionBadgeColor}`}>
            {visionResult}
          </span>

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
        </div>
      </div>
    </div>
  );
}

interface ThumbnailProps {
  url: string;
  label: string;
  loaded: boolean;
  error: boolean;
  onLoad: () => void;
  onError: () => void;
  alignRight?: boolean;
}

function Thumbnail({ url, label, loaded, error, onLoad, onError, alignRight }: ThumbnailProps) {
  return (
    <div className="w-1/2 bg-gray-100 relative">
      {!loaded && !error && <div className="absolute inset-0 bg-gray-200 animate-pulse" />}
      {error ? (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
          {MATCH_CARD_NO_IMAGE}
        </div>
      ) : (
        <img
          src={url}
          alt={label}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
          loading="lazy"
          onLoad={onLoad}
          onError={onError}
        />
      )}
      <div className={`absolute top-1 ${alignRight ? 'right-1' : 'left-1'} bg-black/60 text-white text-xs px-1.5 py-0.5 rounded`}>
        {label}
      </div>
    </div>
  );
}

interface ScoreTooltipProps {
  match: Match;
  show: boolean;
  children: React.ReactNode;
}

function ScoreTooltip({ match, show, children }: ScoreTooltipProps) {
  const hasBreakdown = match.phash_score !== undefined || match.vision_score !== undefined;
  if (!show || !hasBreakdown) return <>{children}</>;

  return (
    <div className="relative">
      {children}
      <div className="absolute right-0 top-full mt-1 bg-white border rounded shadow-lg p-2 text-xs z-10 whitespace-nowrap">
        <div className="space-y-1">
          {match.phash_score !== undefined && (
            <ScoreLine label="PHash" score={match.phash_score} />
          )}
          {match.desc_similarity !== undefined && (
            <ScoreLine label="Desc" score={match.desc_similarity} />
          )}
          {match.vision_score !== undefined && (
            <ScoreLine label="Vision" score={match.vision_score} />
          )}
          <div className="border-t pt-1 mt-1 flex justify-between gap-2 font-medium">
            <span className="text-gray-600">Total:</span>
            <span>{(match.score * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoreLine({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500">{label}:</span>
      <span className="font-mono">{(score * 100).toFixed(0)}%</span>
    </div>
  );
}

function PerspectiveBadge({ match }: { match: Match }) {
  const desc = match.catalog_description;
  if (!desc?.best_perspective) return null;

  const key = desc.best_perspective;
  const perspective = desc.perspectives[key as keyof typeof desc.perspectives];
  if (!perspective) return null;

  return (
    <div className="flex items-center gap-1 mt-0.5">
      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${perspectiveBadgeColor(perspective.score)}`}>
        {PERSPECTIVE_BADGE_LABELS[key] || key} {perspective.score}/10
      </span>
      <span className="text-[9px] text-gray-400">{DESC_BEST_FIT}</span>
    </div>
  );
}
