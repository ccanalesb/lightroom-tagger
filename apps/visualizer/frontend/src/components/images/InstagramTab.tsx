import { useCallback, useEffect, useState } from 'react';
import { PageError, SkeletonGrid } from '../ui/page-states';
import { ImageDetailsModal } from '../instagram/ImageDetailsModal';
import { InstagramImageCard } from '../instagram/InstagramImageCard';
import { Pagination } from '../ui/Pagination';
import { FILTER_ALL_DATES, FILTER_CLEAR, ITEMS_PER_PAGE } from '../../constants/strings';
import { useModal } from '../../hooks/useModal';
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
  const [dateFilter, setDateFilter] = useState('');
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const { isOpen, selectedItem, open, close } = useModal<InstagramImage>();

  const fetchImages = useCallback(
    async (newOffset: number, filter: string = dateFilter) => {
      setIsLoading(true);
      try {
        const params = {
          limit: ITEMS_PER_PAGE,
          offset: newOffset,
          ...(filter && { date_folder: filter }),
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
    [dateFilter]
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

  const handlePageChange = (page: number) => {
    const newOffset = (page - 1) * ITEMS_PER_PAGE;
    fetchImages(newOffset);
  };

  const handleFilterChange = (filter: string) => {
    setDateFilter(filter);
    fetchImages(0, filter);
  };

  const clearFilter = () => {
    setDateFilter('');
    fetchImages(0, '');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">
          {total.toLocaleString()} images total
        </p>

        {availableMonths.length > 0 && (
          <div className="flex items-center space-x-2">
            <select
              value={dateFilter}
              onChange={(e) => handleFilterChange(e.target.value)}
              className="px-3 py-2 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
            >
              <option value="">{FILTER_ALL_DATES}</option>
              {availableMonths.map((month) => (
                <option key={month} value={month}>
                  {formatMonth(month)}
                </option>
              ))}
            </select>
            {dateFilter && (
              <button
                onClick={clearFilter}
                className="px-3 py-2 text-sm rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text transition-all"
              >
                {FILTER_CLEAR}
              </button>
            )}
          </div>
        )}
      </div>

      {error && <PageError message={error} />}
      {isLoading && <SkeletonGrid count={ITEMS_PER_PAGE} />}

      {!isLoading && !error && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {images.map((image) => (
              <InstagramImageCard key={image.key} image={image} onClick={() => open(image)} />
            ))}
          </div>

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

      {isOpen && selectedItem && <ImageDetailsModal image={selectedItem} onClose={close} />}
    </div>
  );
}
