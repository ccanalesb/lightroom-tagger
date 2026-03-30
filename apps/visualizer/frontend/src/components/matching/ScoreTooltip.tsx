import type { Match } from '../../services/api';
import { ScoreLine } from './ScoreLine';

interface ScoreTooltipProps {
  match: Match;
  show: boolean;
  children: React.ReactNode;
}

export function ScoreTooltip({ match, show, children }: ScoreTooltipProps) {
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
          {match.model_used && (
            <div className="border-t pt-1 mt-1 text-gray-400">{match.model_used}</div>
          )}
        </div>
      </div>
    </div>
  );
}
