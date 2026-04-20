import type { ImageView } from '../../../services/api';
import { ImageTile } from '../../image-view';
import type { PrimaryScoreSource } from '../../image-view/ImageMetadataBadges';

interface MatchSideTileProps {
  title: string;
  image: ImageView;
  primaryScoreSource: PrimaryScoreSource;
  onOpenFullDetails: () => void;
}

/**
 * One side of the match comparison — title, tile, and an
 * "Open full details" affordance that launches the canonical
 * `ImageDetailModal` via the caller's click handler.
 */
export function MatchSideTile({
  title,
  image,
  primaryScoreSource,
  onOpenFullDetails,
}: MatchSideTileProps) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-text-secondary">{title}</h4>
      <ImageTile
        image={image}
        variant="compact"
        primaryScoreSource={primaryScoreSource}
        onClick={onOpenFullDetails}
      />
      <div>
        <button
          type="button"
          onClick={onOpenFullDetails}
          className="text-xs text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent rounded-sm"
        >
          Open full details →
        </button>
      </div>
    </div>
  );
}
