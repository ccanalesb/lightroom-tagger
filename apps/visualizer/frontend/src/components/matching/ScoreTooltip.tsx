import type { Match } from '../../services/api';
import {
  MATCH_CARD_SCORE_DESC,
  MATCH_CARD_SCORE_PHASH,
  MATCH_CARD_SCORE_TOTAL,
  MATCH_CARD_SCORE_VISION,
} from '../../constants/strings';
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
            <ScoreLine label={MATCH_CARD_SCORE_PHASH} score={match.phash_score} />
          )}
          {match.desc_similarity !== undefined && (
            <ScoreLine label={MATCH_CARD_SCORE_DESC} score={match.desc_similarity} />
          )}
          {match.vision_score !== undefined && (
            <ScoreLine label={MATCH_CARD_SCORE_VISION} score={match.vision_score} />
          )}
          <div className="border-t pt-1 mt-1 flex justify-between gap-2 font-medium">
            <span className="text-gray-600">{MATCH_CARD_SCORE_TOTAL}</span>
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
