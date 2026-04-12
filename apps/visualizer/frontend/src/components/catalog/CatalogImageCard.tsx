import type { CatalogImage } from '../../services/api';
import { descriptionScoreColor } from '../../utils/scoreColorClasses';
import { DESCRIPTION_PERSPECTIVE_LABELS } from '../DescriptionPanel/perspectiveLabels';
import { Badge } from '../ui/Badge';

interface CatalogImageCardProps {
  image: CatalogImage;
  onClick: () => void;
}

export function CatalogImageCard({ image, onClick }: CatalogImageCardProps) {
  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleDateString()
    : 'No date';

  const best = image.description_best_perspective;
  const perspective =
    best && image.description_perspectives
      ? image.description_perspectives[best as keyof typeof image.description_perspectives]
      : undefined;
  const showScorePill =
    Boolean(best) && perspective != null && typeof perspective.score === 'number';

  const persistedScore = image.catalog_perspective_score;
  const showPersistedScorePill = typeof persistedScore === 'number';
  const scoreSlugShort =
    image.catalog_score_perspective && image.catalog_score_perspective.length > 10
      ? `${image.catalog_score_perspective.slice(0, 10)}…`
      : image.catalog_score_perspective;

  return (
    <div
      onClick={onClick}
      className="bg-bg border border-border rounded-card overflow-hidden shadow-card hover:shadow-deep hover:border-border-strong transition-all cursor-pointer"
    >
      <div className="relative aspect-square bg-surface">
        <img
          src={`/api/images/catalog/${encodeURIComponent(image.key)}/thumbnail`}
          alt={image.filename}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      </div>
      <div className="p-3 space-y-2">
        <p className="text-sm font-medium text-text truncate">{image.filename}</p>
        {image.title && (
          <p className="text-xs text-text-secondary truncate">{image.title}</p>
        )}
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs text-text-tertiary">{dateDisplay}</p>
          {image.instagram_posted && <Badge variant="success">Posted</Badge>}
          {image.rating > 0 && <Badge variant="accent">{image.rating}★</Badge>}
          {image.pick && <Badge variant="accent">Pick</Badge>}
          {image.ai_analyzed && <Badge variant="accent">AI</Badge>}
          {showScorePill && best && perspective && (
            <span
              className={`text-xs px-1.5 py-0.5 rounded font-medium ${descriptionScoreColor(perspective.score)}`}
            >
              {DESCRIPTION_PERSPECTIVE_LABELS[best] || best} {perspective.score}/10
            </span>
          )}
          {showPersistedScorePill && (
            <Badge variant="default" className="!px-1.5 !py-0.5 text-[10px] font-medium opacity-90">
              {scoreSlugShort ? `${scoreSlugShort} ` : ''}
              {persistedScore}/10
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}
