import type { Match } from '../../../services/api';
import { DescriptionPanel } from '../../DescriptionPanel';
import {
  DESC_PANEL_TITLE,
  MATCH_DETAIL_INSTAGRAM,
  MATCH_DETAIL_CATALOG,
} from '../../../constants/strings';

interface MatchDescriptionsSectionProps {
  match: Match;
}

export function MatchDescriptionsSection({ match }: MatchDescriptionsSectionProps) {
  if (!match.catalog_description && !match.insta_description) {
    return null;
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {match.insta_description && (
        <div className="bg-gray-50 p-3 rounded-lg">
          <h4 className="text-xs font-medium text-gray-500 mb-2">
            {MATCH_DETAIL_INSTAGRAM} — {DESC_PANEL_TITLE}
          </h4>
          <DescriptionPanel description={match.insta_description} />
        </div>
      )}
      {match.catalog_description && (
        <div
          className={`bg-gray-50 p-3 rounded-lg ${!match.insta_description ? 'col-span-2' : ''}`}
        >
          <h4 className="text-xs font-medium text-gray-500 mb-2">
            {MATCH_DETAIL_CATALOG} — {DESC_PANEL_TITLE}
          </h4>
          <DescriptionPanel description={match.catalog_description} />
        </div>
      )}
    </div>
  );
}
