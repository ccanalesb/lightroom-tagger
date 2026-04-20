import type { Match } from '../../../services/api';
import { AIDescriptionSection } from '../../DescriptionPanel';
import {
  IMAGE_DETAILS_AI_DESCRIPTION,
  MATCH_DETAIL_INSTAGRAM,
  MATCH_DETAIL_CATALOG,
} from '../../../constants/strings';

interface MatchDescriptionsSectionProps {
  match: Match;
}

/**
 * Side-by-side AI descriptions for the IG and catalog sides of a match.
 * Uses the shared `AIDescriptionSection` so the panel, generate button,
 * and model options look identical to every other image modal.
 */
export function MatchDescriptionsSection({ match }: MatchDescriptionsSectionProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <AIDescriptionSection
        imageKey={match.instagram_key}
        imageType="instagram"
        titleOverride={`${MATCH_DETAIL_INSTAGRAM} — ${IMAGE_DETAILS_AI_DESCRIPTION}`}
      />
      <AIDescriptionSection
        imageKey={match.catalog_key}
        imageType="catalog"
        titleOverride={`${MATCH_DETAIL_CATALOG} — ${IMAGE_DETAILS_AI_DESCRIPTION}`}
      />
    </div>
  );
}
