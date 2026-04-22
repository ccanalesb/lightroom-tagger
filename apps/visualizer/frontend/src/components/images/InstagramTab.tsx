import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PageError, SkeletonGrid } from '../ui/page-states';
import { ImageDetailModal, ImageTile, fromInstagramRow } from '../image-view';
import { Badge } from '../ui/badges';
import { Pagination } from '../ui/Pagination';
import { TileGrid } from '../ui/TileGrid';
import {
  BADGE_DESCRIBED,
  BADGE_MATCHED,
  FILTER_ALL_DATES,
  FILTER_LABEL_SORT_DATE,
  FILTER_SORT_DATE_NEWEST,
  FILTER_SORT_DATE_OLDEST,
  ITEMS_PER_PAGE,
  msgShowingOf,
} from '../../constants/strings';
import { useModal } from '../../hooks/useModal';
import { useFilters } from '../../hooks/useFilters';
import { FilterBar } from '../filters/FilterBar';
import type { FilterSchema } from '../filters/types';
import type { InstagramImage } from '../../services/api';
import { ImagesAPI } from '../../services/api';
import { formatMonth } from '../../utils/date';

export function InstagramTab() {
  const [images, setImages] = useState<InstagramImage[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    current_page: 1,
    total_pages: 1,
    has_more: false,
  });
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const { isOpen, selectedItem, open, close } = useModal<InstagramImage>();

  const instagramSchema = useMemo<FilterSchema>(
    () => [
      {
        type: 'select',
        key: 'dateFolder',
        label: 'Date',
        paramName: 'date_folder',
        defaultValue: '',
        options: [
          { value: '', label: FILTER_ALL_DATES },
          ...availableMonths.map((month) => ({
            value: month,
            label: formatMonth(month),
          })),
        ],
      },
      {
        type: 'select',
        key: 'sortByDate',
        label: FILTER_LABEL_SORT_DATE,
        paramName: 'sort_by_date',
        defaultValue: 'newest',
        options: [
          { value: 'newest', label: FILTER_SORT_DATE_NEWEST },
          { value: 'oldest', label: FILTER_SORT_DATE_OLDEST },
        ],
      },
    ],
    [availableMonths],
  );

  const filters = useFilters(instagramSchema);
  const { values: filterValues, toQueryParams } = filters;
  const dateFolder = filterValues.dateFolder as string | undefined;
  const sortByDate = filterValues.sortByDate as string | undefined;

  const fetchImages = useCallback(
    async (newOffset: number) => {
      setIsLoading(true);
      try {
        const params = {
          ...toQueryParams(),
          limit: ITEMS_PER_PAGE,
          offset: newOffset,
        };
        const data = await ImagesAPI.listInstagram(params);
        setImages(data.images);
        setTotal(data.total);
        setPagination(data.pagination);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    },
    [toQueryParams],
  );

  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true);
      try {
        const [monthsData, firstPageData] = await Promise.all([
          ImagesAPI.getInstagramMonths(),
          ImagesAPI.listInstagram({ limit: ITEMS_PER_PAGE, offset: 0 }),
        ]);
        setAvailableMonths(monthsData.months);
        setImages(firstPageData.images);
        setTotal(firstPageData.total);
        setPagination(firstPageData.pagination);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };
    initialize();
  }, []);

  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    fetchImages(0);
  }, [dateFolder, sortByDate, fetchImages]);

  const handlePageChange = (page: number) => {
    const newOffset = (page - 1) * ITEMS_PER_PAGE;
    fetchImages(newOffset);
  };

  return (
    <div className="space-y-6">
      <FilterBar
        schema={instagramSchema}
        filters={filters}
        summary={
          <p className="text-sm text-text-secondary">
            {msgShowingOf(images.length, total, 'images')}
          </p>
        }
        disabled={isLoading}
      />

      {error && <PageError message={error} />}
      {isLoading && <SkeletonGrid count={ITEMS_PER_PAGE} />}

      {!isLoading && !error && (
        <>
          <TileGrid>
            {images.map((image) => (
              <ImageTile
                key={image.key}
                image={fromInstagramRow(image)}
                variant="grid"
                primaryScoreSource="none"
                subtitle={image.instagram_folder || image.source_folder || undefined}
                overlayBadges={renderInstagramOverlayBadges(image)}
                onClick={() => open(image)}
              />
            ))}
          </TileGrid>

          {pagination.total_pages > 1 && (
            <div className="flex justify-center pt-4">
              <Pagination
                currentPage={pagination.current_page}
                totalPages={pagination.total_pages}
                onPageChange={handlePageChange}
              />
            </div>
          )}
        </>
      )}

      {isOpen && selectedItem && (
        <ImageDetailModal
          imageType="instagram"
          imageKey={selectedItem.key}
          initialImage={fromInstagramRow(selectedItem)}
          primaryScoreSource="none"
          onClose={close}
        />
      )}
    </div>
  );
}

/**
 * Overlay badges shown on an Instagram tile:
 *   - "Matched" when the image has a validated catalog match.
 *   - "Described" when the image has an AI description.
 * Both can render together.
 */
function renderInstagramOverlayBadges(image: InstagramImage) {
  return (
    <>
      {image.matched_catalog_key ? <Badge variant="success">{BADGE_MATCHED}</Badge> : null}
      {image.description ? <Badge variant="accent">{BADGE_DESCRIBED}</Badge> : null}
    </>
  );
}
