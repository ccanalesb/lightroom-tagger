import { useCallback, useEffect, useState } from 'react';
import { ImagesAPI, type CatalogImage } from '../../services/api';
import { CatalogImageCard } from '../catalog/CatalogImageCard';
import { CatalogImageModal } from '../catalog/CatalogImageModal';
import { Input } from '../ui/Input';
import { Pagination } from '../ui/Pagination';
import { FILTER_CLEAR, FILTER_ALL_DATES } from '../../constants/strings';
import { formatMonth } from '../../utils/date';

const LIMIT = 50;

export function CatalogTab() {
  const [images, setImages] = useState<CatalogImage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [catalogFetchSucceeded, setCatalogFetchSucceeded] = useState(false);
  const [selectedImage, setSelectedImage] = useState<CatalogImage | null>(null);
  const [postedFilter, setPostedFilter] = useState<boolean | undefined>(undefined);
  const [monthFilter, setMonthFilter] = useState<string>('');
  const [keyword, setKeyword] = useState('');
  const [minRating, setMinRating] = useState<number | ''>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [colorLabel, setColorLabel] = useState('');
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);

  const loadImages = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const offset = (page - 1) * LIMIT;
      const kw = keyword.trim();
      const cl = colorLabel.trim();
      const data = await ImagesAPI.listCatalog({
        ...(postedFilter !== undefined ? { posted: postedFilter } : {}),
        ...(monthFilter ? { month: monthFilter } : {}),
        ...(kw ? { keyword: kw } : {}),
        ...(minRating !== '' ? { min_rating: minRating } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
        ...(cl ? { color_label: cl } : {}),
        limit: LIMIT,
        offset,
      });
      setImages(data.images);
      setTotal(data.total);
      setCatalogFetchSucceeded(true);
    } catch (err) {
      console.error('Failed to load catalog images:', err);
      const message = err instanceof Error ? err.message : 'Failed to load catalog images';
      setLoadError(message);
      setImages([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [
    page,
    postedFilter,
    monthFilter,
    keyword,
    minRating,
    dateFrom,
    dateTo,
    colorLabel,
  ]);

  useEffect(() => {
    const fetchMonths = async () => {
      try {
        const data = await ImagesAPI.getCatalogMonths();
        setAvailableMonths(data.months);
      } catch (err) {
        console.error('Failed to load months:', err);
      }
    };
    fetchMonths();
  }, []);

  useEffect(() => {
    loadImages();
  }, [loadImages]);

  const handlePostedFilterChange = (filter: string) => {
    if (filter === 'all') {
      setPostedFilter(undefined);
    } else if (filter === 'posted') {
      setPostedFilter(true);
    } else if (filter === 'not-posted') {
      setPostedFilter(false);
    }
    setPage(1);
  };

  const handleMonthFilterChange = (month: string) => {
    setMonthFilter(month);
    setPage(1);
  };

  const handleKeywordChange = (value: string) => {
    setKeyword(value);
    setPage(1);
  };

  const handleMinRatingChange = (value: string) => {
    if (value === '') setMinRating('');
    else setMinRating(Number(value));
    setPage(1);
  };

  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    setPage(1);
  };

  const handleDateToChange = (value: string) => {
    setDateTo(value);
    setPage(1);
  };

  const handleColorLabelChange = (value: string) => {
    setColorLabel(value);
    setPage(1);
  };

  const clearFilters = () => {
    setPostedFilter(undefined);
    setMonthFilter('');
    setKeyword('');
    setMinRating('');
    setDateFrom('');
    setDateTo('');
    setColorLabel('');
    setPage(1);
  };

  const hasActiveFilters =
    postedFilter !== undefined ||
    Boolean(monthFilter) ||
    Boolean(keyword.trim()) ||
    minRating !== '' ||
    Boolean(dateFrom) ||
    Boolean(dateTo) ||
    Boolean(colorLabel.trim());

  const noFiltersAndEmptyDb =
    catalogFetchSucceeded && !loadError && total === 0 && !hasActiveFilters;

  const totalPages = Math.ceil(total / LIMIT);

  const summaryText = (() => {
    if (loading && !loadError) {
      return 'Loading catalog images…';
    }
    if (loadError) {
      return 'Could not load the catalog list.';
    }
    if (total === 0 && hasActiveFilters) {
      return 'No images match the filters';
    }
    return `Showing ${images.length} of ${total.toLocaleString()} images`;
  })();

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-text-secondary">{summaryText}</p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              disabled={loading}
              className="px-3 py-1.5 text-sm rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text transition-all disabled:opacity-60"
            >
              {FILTER_CLEAR}
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">Status</span>
            <select
              value={
                postedFilter === undefined ? 'all' : postedFilter ? 'posted' : 'not-posted'
              }
              onChange={(e) => handlePostedFilterChange(e.target.value)}
              disabled={loading}
              className="h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60"
            >
              <option value="all">All Images</option>
              <option value="posted">Posted</option>
              <option value="not-posted">Not Posted</option>
            </select>
          </div>

          {availableMonths.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-text-tertiary">Month</span>
              <select
                value={monthFilter}
                onChange={(e) => handleMonthFilterChange(e.target.value)}
                disabled={loading}
                className="h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60"
              >
                <option value="">{FILTER_ALL_DATES}</option>
                {availableMonths.map((month) => (
                  <option key={month} value={month}>
                    {formatMonth(month)}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">Keyword</span>
            <Input
              type="search"
              placeholder="Search…"
              value={keyword}
              onChange={(e) => handleKeywordChange(e.target.value)}
              className="h-9 min-w-[8rem] w-36"
              aria-label="Keyword search"
              disabled={loading}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">Min rating</span>
            <select
              value={minRating === '' ? '' : String(minRating)}
              onChange={(e) => handleMinRatingChange(e.target.value)}
              disabled={loading}
              className="h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60"
            >
              <option value="">Any</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{'★'.repeat(n)}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => handleDateFromChange(e.target.value)}
              disabled={loading}
              className="h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => handleDateToChange(e.target.value)}
              disabled={loading}
              className="h-9 px-3 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-text-tertiary">Color label</span>
            <Input
              placeholder="e.g. Red"
              value={colorLabel}
              onChange={(e) => handleColorLabelChange(e.target.value)}
              className="h-9 min-w-[6rem] w-28"
              aria-label="Color label"
              disabled={loading}
            />
          </div>
        </div>
      </div>

      {loading && !loadError ? (
        <div className="text-center py-12">
          <p className="text-text-secondary">Loading catalog images…</p>
        </div>
      ) : loadError ? (
        <div className="rounded-base border border-border bg-surface px-4 py-6 text-center">
          <h3 className="text-sm font-medium text-text">Catalog list failed</h3>
          <p className="mt-2 text-sm text-text-secondary">{loadError}</p>
          <p className="mt-3 text-xs text-text-tertiary">
            Check the catalog path above, then adjust filters or reload the page to retry.
          </p>
        </div>
      ) : noFiltersAndEmptyDb ? (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-text">No Catalog Images</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Your catalog database is empty or not yet indexed.
          </p>
        </div>
      ) : total === 0 && hasActiveFilters ? (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-text">No Images Found</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Try changing or clearing the filters.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {images.map((image) => (
              <CatalogImageCard
                key={image.id != null ? String(image.id) : image.key}
                image={image}
                onClick={() => setSelectedImage(image)}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      {selectedImage && (
        <CatalogImageModal
          image={selectedImage}
          onClose={() => setSelectedImage(null)}
        />
      )}
    </div>
  );
}
