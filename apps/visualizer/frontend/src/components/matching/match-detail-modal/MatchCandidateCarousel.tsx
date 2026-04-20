import { MATCH_CANDIDATE_LABEL } from '../../../constants/strings';

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
      <ArrowButton dir={-1} label="Previous candidate" glyph="‹" onClick={() => onStep(-1)} />
      <span className="text-sm text-text-secondary tabular-nums min-w-[7ch] text-center">
        {MATCH_CANDIDATE_LABEL} {activeIndex + 1} of {total}
      </span>
      <ArrowButton dir={1} label="Next candidate" glyph="›" onClick={() => onStep(1)} />
    </div>
  );
}

interface ArrowButtonProps {
  dir: -1 | 1;
  label: string;
  glyph: string;
  onClick: () => void;
}

function ArrowButton({ label, glyph, onClick }: ArrowButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="w-8 h-8 flex items-center justify-center rounded-full border text-lg border-border text-text hover:bg-surface"
    >
      {glyph}
    </button>
  );
}
