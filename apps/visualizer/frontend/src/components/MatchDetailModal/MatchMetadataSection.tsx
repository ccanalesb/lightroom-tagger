import type { Match } from '../../services/api';
import {
  MATCH_DETAIL_MATCH_DETAILS,
  MATCH_DETAIL_INSTAGRAM_KEY,
  MATCH_DETAIL_CATALOG_KEY,
} from '../../constants/strings';

interface MatchMetadataSectionProps {
  match: Match;
}

export function MatchMetadataSection({ match }: MatchMetadataSectionProps) {
  return (
    <div className="bg-gray-50 p-4 rounded-lg text-sm space-y-2">
      <h4 className="font-medium text-gray-700">{MATCH_DETAIL_MATCH_DETAILS}</h4>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-gray-500">{MATCH_DETAIL_INSTAGRAM_KEY}</span>
          <p className="font-mono text-xs break-all">{match.instagram_key}</p>
        </div>
        <div>
          <span className="text-gray-500">{MATCH_DETAIL_CATALOG_KEY}</span>
          <p className="font-mono text-xs break-all">{match.catalog_key}</p>
        </div>
      </div>
    </div>
  );
}
