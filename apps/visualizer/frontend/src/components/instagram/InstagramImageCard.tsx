import type { InstagramImage } from '../../services/api';
import { Badge } from '../ui/Badge';
import {
  BADGE_MATCHED,
  BADGE_DESCRIBED,
  DATE_NO_DATE,
  DATE_ESTIMATED_SUFFIX,
} from '../../constants/strings';

interface InstagramImageCardProps {
  image: InstagramImage;
  onClick: () => void;
}

export function InstagramImageCard({ image, onClick }: InstagramImageCardProps) {
  const dateDisplay = image.created_at
    ? new Date(image.created_at).toLocaleDateString()
    : image.date_folder
      ? `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} ${DATE_ESTIMATED_SUFFIX}`
      : DATE_NO_DATE;

  return (
    <div
      onClick={onClick}
      className="group cursor-pointer bg-bg rounded-card border border-border overflow-hidden shadow-card hover:shadow-deep hover:border-border-strong transition-all duration-200"
    >
      <div className="relative aspect-square bg-surface">
        <img
          src={`/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`}
          alt={image.filename}
          className="absolute inset-0 w-full h-full object-cover"
          loading="lazy"
        />

        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-200" />

        <div className="absolute top-2 right-2 flex flex-col gap-1">
          {image.matched_catalog_key && <Badge variant="success">{BADGE_MATCHED}</Badge>}
          {image.description && <Badge variant="accent">{BADGE_DESCRIBED}</Badge>}
        </div>
      </div>

      <div className="p-3 space-y-1">
        <p className="text-sm font-medium text-text truncate">{image.instagram_folder}</p>
        <p className="text-xs text-text-tertiary">{image.source_folder}</p>
        <p className="text-xs text-text-secondary">{dateDisplay}</p>
      </div>
    </div>
  );
}
