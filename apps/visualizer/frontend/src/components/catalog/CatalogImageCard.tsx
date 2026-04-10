import type { CatalogImage } from '../../services/api';
import { Badge } from '../ui/Badge';

interface CatalogImageCardProps {
  image: CatalogImage;
  onClick: () => void;
}

export function CatalogImageCard({ image, onClick }: CatalogImageCardProps) {
  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleDateString()
    : 'No date';

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
        </div>
      </div>
    </div>
  );
}
