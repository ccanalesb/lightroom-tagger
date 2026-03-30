import type { Match } from '../../../services/api';
import { MATCH_CANDIDATE_LABEL } from '../../../constants/strings';

interface CandidateTabBarProps {
  candidates: Match[];
  activeKey: string;
  onSelect: (candidate: Match) => void;
}

export function CandidateTabBar({ candidates, activeKey, onSelect }: CandidateTabBarProps) {
  if (candidates.length <= 1) return null;

  return (
    <div className="flex gap-1 p-2 bg-gray-50 border-b overflow-x-auto">
      {candidates.map((c, i) => {
        const isActive = c.catalog_key === activeKey;
        return (
          <button
            key={c.catalog_key}
            type="button"
            onClick={() => onSelect(c)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap transition-colors ${
              isActive
                ? 'bg-blue-600 text-white'
                : 'bg-white border text-gray-600 hover:bg-gray-100'
            }`}
          >
            <span>
              {MATCH_CANDIDATE_LABEL} {i + 1}
            </span>
            <span className={isActive ? 'text-blue-200' : 'text-gray-400'}>
              {(c.score * 100).toFixed(0)}%
            </span>
            {c.validated_at && <span>✓</span>}
          </button>
        );
      })}
    </div>
  );
}
