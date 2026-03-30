import { useState, useCallback } from 'react';
import type { MouseEvent } from 'react';
import { Thumbnail } from '../ui/Thumbnail';
import {
  MATCH_CARD_CATALOG_LABEL,
  MATCH_CARD_NO_IMAGE,
  MATCH_CANDIDATES_OF,
} from '../../constants/strings';
import { thumbnailUrl } from '../../utils/imageUrl';

interface CandidateCarouselProps {
  catalogKeys: string[];
  activeIndex: number;
  onIndexChange: (index: number) => void;
}

export function CandidateCarousel({
  catalogKeys,
  activeIndex,
  onIndexChange,
}: CandidateCarouselProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const multi = catalogKeys.length > 1;

  const resetImage = useCallback(() => {
    setLoaded(false);
    setError(false);
  }, []);

  const prev = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    const next = activeIndex > 0 ? activeIndex - 1 : catalogKeys.length - 1;
    onIndexChange(next);
    resetImage();
  };

  const next = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    const nextIdx = activeIndex < catalogKeys.length - 1 ? activeIndex + 1 : 0;
    onIndexChange(nextIdx);
    resetImage();
  };

  const src = thumbnailUrl('catalog', catalogKeys[activeIndex]);

  return (
    <div className="w-1/2 relative">
      <Thumbnail
        url={src}
        label={MATCH_CARD_CATALOG_LABEL}
        loaded={loaded}
        error={error}
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        alignRight
        errorText={MATCH_CARD_NO_IMAGE}
      />
      {multi && (
        <>
          <button
            type="button"
            onClick={prev}
            className="absolute left-0 top-1/2 -translate-y-1/2 bg-black/40 text-white px-1.5 py-3 rounded-r text-sm hover:bg-black/60 z-10"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={next}
            className="absolute right-0 top-1/2 -translate-y-1/2 bg-black/40 text-white px-1.5 py-3 rounded-l text-sm hover:bg-black/60 z-10"
          >
            ›
          </button>
          <span className="absolute bottom-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded z-10">
            {activeIndex + 1} {MATCH_CANDIDATES_OF} {catalogKeys.length}
          </span>
        </>
      )}
    </div>
  );
}
