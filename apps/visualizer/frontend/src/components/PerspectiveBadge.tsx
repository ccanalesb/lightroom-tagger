import type { Match } from '../services/api';
import {
  DESC_BEST_FIT,
  DESC_PERSPECTIVE_STREET,
  DESC_PERSPECTIVE_DOCUMENTARY,
  DESC_PERSPECTIVE_PUBLISHER,
} from '../constants/strings';
import { perspectiveBadgeColor } from '../utils/scoreColorClasses';

const PERSPECTIVE_BADGE_LABELS: Record<string, string> = {
  street: DESC_PERSPECTIVE_STREET,
  documentary: DESC_PERSPECTIVE_DOCUMENTARY,
  publisher: DESC_PERSPECTIVE_PUBLISHER,
};

export function PerspectiveBadge({ match }: { match: Match }) {
  const desc = match.insta_description ?? match.catalog_description;
  if (!desc?.best_perspective) return null;

  const key = desc.best_perspective;
  const perspective = desc.perspectives[key as keyof typeof desc.perspectives];
  if (!perspective) return null;

  return (
    <div className="flex items-center gap-1 mt-0.5">
      <span
        className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${perspectiveBadgeColor(perspective.score)}`}
      >
        {PERSPECTIVE_BADGE_LABELS[key] || key} {perspective.score}/10
      </span>
      <span className="text-[9px] text-gray-400">{DESC_BEST_FIT}</span>
    </div>
  );
}
