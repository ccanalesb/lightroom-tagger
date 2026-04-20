import { useCallback, useRef, useState } from 'react';
import type { Match } from '../../../services/api';
import {
  MATCH_DETAIL_INSTAGRAM,
  MATCH_DETAIL_CATALOG,
} from '../../../constants/strings';
import { ImageDetailModal, fromMatchSide } from '../../image-view';
import { MatchSideTile } from './MatchSideTile';
import { MatchCandidateCarousel } from './MatchCandidateCarousel';
import { useCandidateKeyboardNav } from './useCandidateKeyboardNav';

interface MatchImagesSectionProps {
  /** The full candidate list in stable order (rank 1 first). */
  candidates: Match[];
  /** The currently shown candidate (must be in `candidates`). */
  activeMatch: Match;
  onCandidateChange: (match: Match) => void;
}

/**
 * Side-by-side comparison (stacked on mobile): the Instagram image
 * alongside the currently-selected catalog candidate, with
 * `‹ N of M ›` carousel controls below. Arrow keys step through
 * candidates when the modal has focus.
 *
 * Each side exposes an "Open full details" affordance that launches
 * the canonical `ImageDetailModal` on top for full metadata parity.
 */
export function MatchImagesSection({
  candidates,
  activeMatch,
  onCandidateChange,
}: MatchImagesSectionProps) {
  const [openSide, setOpenSide] = useState<null | 'instagram' | 'catalog'>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const activeIndex = candidates.findIndex(
    (c) =>
      c.catalog_key === activeMatch.catalog_key &&
      c.instagram_key === activeMatch.instagram_key,
  );
  const total = candidates.length;

  const step = useCallback(
    (delta: -1 | 1) => {
      if (total <= 1) return;
      const nextIndex = (activeIndex + delta + total) % total;
      onCandidateChange(candidates[nextIndex]);
    },
    [activeIndex, total, candidates, onCandidateChange],
  );

  useCandidateKeyboardNav(total > 1, containerRef, step);

  const instagramView = fromMatchSide(activeMatch, 'instagram');
  const catalogView = fromMatchSide(activeMatch, 'catalog');

  return (
    <>
      <div ref={containerRef} tabIndex={-1} className="space-y-3 focus:outline-none">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <MatchSideTile
            title={MATCH_DETAIL_INSTAGRAM}
            image={instagramView}
            primaryScoreSource="none"
            onOpenFullDetails={() => setOpenSide('instagram')}
          />
          <MatchSideTile
            title={MATCH_DETAIL_CATALOG}
            image={catalogView}
            primaryScoreSource="catalog"
            onOpenFullDetails={() => setOpenSide('catalog')}
          />
        </div>

        <MatchCandidateCarousel
          activeIndex={activeIndex}
          total={total}
          onStep={step}
        />
      </div>

      {openSide === 'instagram' ? (
        <ImageDetailModal
          imageType="instagram"
          imageKey={activeMatch.instagram_key}
          initialImage={instagramView}
          primaryScoreSource="none"
          onClose={() => setOpenSide(null)}
        />
      ) : null}
      {openSide === 'catalog' ? (
        <ImageDetailModal
          imageType="catalog"
          imageKey={activeMatch.catalog_key}
          initialImage={catalogView}
          primaryScoreSource="catalog"
          onClose={() => setOpenSide(null)}
        />
      ) : null}
    </>
  );
}
