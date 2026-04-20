import { MATCH_CANDIDATE_LABEL } from '../../../constants/strings';
import { CarouselArrowButton } from './CarouselArrowButton';

interface MatchCandidateCarouselProps {
  activeIndex: number;
  total: number;
  onStep: (delta: -1 | 1) => void;
}

/**
 * `‹ N of M ›` carousel strip used below the match comparison tiles.
 * Renders nothing when there's only one candidate.
 */
export function MatchCandidateCarousel({
  activeIndex,
  total,
  onStep,
}: MatchCandidateCarouselProps) {
  if (total <= 1) return null;

  return (
    <div
      className="flex items-center justify-center gap-3 pt-1"
      aria-label="Candidate carousel"
    >
      <CarouselArrowButton label="Previous candidate" glyph="‹" onClick={() => onStep(-1)} />
      <span className="text-sm text-text-secondary tabular-nums min-w-[7ch] text-center">
        {MATCH_CANDIDATE_LABEL} {activeIndex + 1} of {total}
      </span>
      <CarouselArrowButton label="Next candidate" glyph="›" onClick={() => onStep(1)} />
    </div>
  );
}
