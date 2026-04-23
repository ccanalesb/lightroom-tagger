import { useEffect, useMemo, useState } from 'react';
import { ImageDetailModal, ImageTile, fromInstagramRow } from '../image-view';
import { Badge } from '../ui/badges';
import { Pagination } from '../ui/Pagination';
import { TileGrid } from '../ui/TileGrid';
import {
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
import { useQuery } from '../../data';
import { stableSerializeRecord } from '../../utils/stableQueryKey';

export function InstagramTab() {
  const [page, setPage] = useState(1);

  const monthsPayload = useQuery(['images.instagram', 'months'] as const, () =>
    ImagesAPI.getInstagramMonths(),
  );
  const availableMonths = monthsPayload.months;

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

  const listParams = useMemo(
    () => ({
      ...toQueryParams(),
      limit: ITEMS_PER_PAGE,
      offset: (page - 1) * ITEMS_PER_PAGE,
    }),
    [page, toQueryParams, dateFolder, sortByDate],
  );

  const listKey = useMemo(
    () => ['images.instagram', 'list', stableSerializeRecord(listParams)] as const,
    [listParams],
  );

  const listData = useQuery(listKey, () => ImagesAPI.listInstagram(listParams));
  const images = listData.images;
  const total = listData.total;
  const pagination = listData.pagination;

  useEffect(() => {
    setPage(1);
  }, [dateFolder, sortByDate]);

  const handlePageChange = (nextPage: number) => {
    setPage(nextPage);
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
        disabled={false}
      />

      <TileGrid>
        {images.map((image) => (
          <ImageTile
            key={image.key}
            image={fromInstagramRow(image)}
            variant="grid"
            primaryScoreSource="none"
            subtitle={image.instagram_folder || image.source_folder || undefined}
            footer={
              image.matched_catalog_key ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success">{BADGE_MATCHED}</Badge>
                  {typeof image.match_score === 'number' && (
                    <Badge variant="default">{Math.round(image.match_score * 100)}%</Badge>
                  )}
                </div>
              ) : null
            }
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
