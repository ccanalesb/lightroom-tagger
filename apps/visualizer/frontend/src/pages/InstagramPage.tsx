import { useCallback, useEffect, useState } from "react";
import { PageError, SkeletonGrid } from "../components/ui/page-states";
import { ImageDetailsModal } from "../components/instagram/ImageDetailsModal";
import { InstagramImageCard } from "../components/instagram/InstagramImageCard";
import { Pagination } from "../components/ui/Pagination";
import {
  FILTER_ALL_DATES,
  FILTER_CLEAR,
  INSTAGRAM_DOWNLOADED,
  ITEMS_PER_PAGE,
} from "../constants/strings";
import { useModal } from "../hooks/useModal";
import type { InstagramImage } from "../services/api";
import { ImagesAPI } from "../services/api";
import { formatMonth } from "../utils/date";

export function InstagramPage() {
  const [images, setImages] = useState<InstagramImage[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    current_page: 1,
    total_pages: 1,
    has_more: false,
  });
  const [dateFilter, setDateFilter] = useState("");
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const {
    isOpen: isModalOpen,
    selectedItem: selectedImage,
    open: openModal,
    close: closeModal,
  } = useModal<InstagramImage>();

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
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setIsLoading(false);
      }
    },
    [dateFilter],
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
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setIsLoading(false);
      }
    };

    initialize();
  }, []);

  const handleDateFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newFilter = e.target.value;
    setDateFilter(newFilter);
    fetchImages(0, newFilter);
  };

  const clearDateFilter = () => {
    setDateFilter("");
    fetchImages(0, "");
  };

  if (error) return <PageError message={error} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl font-bold text-gray-900">
          {INSTAGRAM_DOWNLOADED}
        </h2>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <select
              value={dateFilter}
              onChange={handleDateFilterChange}
              className="text-sm border border-gray-300 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                onClick={clearDateFilter}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                {FILTER_CLEAR}
              </button>
            )}
          </div>

          <p className="text-sm text-gray-500">{total} images</p>
        </div>
      </div>

      {isLoading && images.length === 0 ? (
        <SkeletonGrid count={12} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {images.map((image) => (
              <InstagramImageCard
                key={image.key}
                image={image}
                onClick={() => openModal(image)}
              />
            ))}
          </div>

          <Pagination
            currentPage={pagination.current_page}
            totalPages={pagination.total_pages}
            onPageChange={(page) => fetchImages((page - 1) * ITEMS_PER_PAGE, dateFilter)}
            disabled={isLoading}
          />
        </>
      )}

      {isModalOpen && selectedImage && (
        <ImageDetailsModal image={selectedImage} onClose={closeModal} />
      )}
    </div>
  );
}
