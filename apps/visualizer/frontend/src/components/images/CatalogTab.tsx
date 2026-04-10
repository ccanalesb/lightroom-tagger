import { useCallback, useEffect, useState } from 'react';
import { ImagesAPI, type CatalogImage } from '../../services/api';
import { CatalogSettingsPanel } from './CatalogSettingsPanel';
import { CatalogImageCard } from '../catalog/CatalogImageCard';
import { CatalogImageModal } from '../catalog/CatalogImageModal';
import { Pagination } from '../ui/Pagination';
import { FILTER_CLEAR, FILTER_ALL_DATES } from '../../constants/strings';
import { formatMonth } from '../../utils/date';

const LIMIT = 50;

export function CatalogTab() {
  const [images, setImages] = useState<CatalogImage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState<CatalogImage | null>(null);
  const [postedFilter, setPostedFilter] = useState<boolean | undefined>(undefined);
  const [monthFilter, setMonthFilter] = useState<string>('');
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);

  const loadImages = useCallback(async () => {
    try {
      setLoading(true);
      const offset = (page - 1) * LIMIT;
      const data = await ImagesAPI.listCatalog(
        postedFilter,
        monthFilter || undefined,
        LIMIT,
        offset
      );
      setImages(data.images);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load catalog images:', err);
    } finally {
      setLoading(false);
    }
  }, [page, postedFilter, monthFilter]);

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

  const clearFilters = () => {
    setPostedFilter(undefined);
    setMonthFilter('');
    setPage(1);
  };

  const totalPages = Math.ceil(total / LIMIT);

  if (loading) {
    return (
      <div className="space-y-6">
        <CatalogSettingsPanel />
        <div className="text-center py-12">
          <p className="text-text-secondary">Loading catalog images...</p>
        </div>
      </div>
    );
  }

  if (total === 0 && postedFilter === undefined && !monthFilter) {
    return (
      <div className="space-y-6">
        <CatalogSettingsPanel />
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-text">No Catalog Images</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Your catalog database is empty or not yet indexed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <CatalogSettingsPanel />
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">
          {total === 0 && (postedFilter !== undefined || monthFilter)
            ? 'No images match the filters'
            : `Showing ${images.length} of ${total.toLocaleString()} images`}
        </p>

        <div className="flex items-center space-x-2">
          <select
            value={
              postedFilter === undefined ? 'all' : postedFilter ? 'posted' : 'not-posted'
            }
            onChange={(e) => handlePostedFilterChange(e.target.value)}
            className="px-3 py-2 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
          >
            <option value="all">All Images</option>
            <option value="posted">Posted to Instagram</option>
            <option value="not-posted">Not Posted</option>
          </select>

          {availableMonths.length > 0 && (
            <select
              value={monthFilter}
              onChange={(e) => handleMonthFilterChange(e.target.value)}
              className="px-3 py-2 rounded-base border border-border bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
            >
              <option value="">{FILTER_ALL_DATES}</option>
              {availableMonths.map((month) => (
                <option key={month} value={month}>
                  {formatMonth(month)}
                </option>
              ))}
            </select>
          )}

          {(postedFilter !== undefined || monthFilter) && (
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-sm rounded-base border border-border bg-bg text-text-secondary hover:bg-surface hover:text-text transition-all"
            >
              {FILTER_CLEAR}
            </button>
          )}
        </div>
      </div>

      {total === 0 && (postedFilter !== undefined || monthFilter) ? (
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
                key={image.id}
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
