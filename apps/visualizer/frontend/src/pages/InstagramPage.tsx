import { useCallback, useEffect, useRef, useState } from "react";
import { AdvancedOptions } from "../components";
import { MetadataRow, MetadataSection } from "../components/metadata";
import { ExifDataSection } from "../components/metadata/ExifDataSection";
import { Modal, ModalFooter, ModalHeader } from "../components/modal";
import {
  FILTER_ALL_DATES,
  FILTER_CLEAR,
  HASH_EXPLANATION,
  INSTAGRAM_DOWNLOADED,
  ITEMS_PER_PAGE,
  LABEL_ADDED,
  LABEL_DATE_FOLDER,
  LABEL_FILENAME,
  LABEL_MEDIA_KEY,
  LABEL_SOURCE_FOLDER,
  LABEL_VISUAL_HASH,
  META_SECTION_BASIC_INFO,
  META_SECTION_CAPTION,
  META_SECTION_FILE_LOCATION,
  META_SECTION_IMAGE_ANALYSIS,
  MODAL_CLOSE,
  MODAL_MATCH_RESULT_FOUND,
  MODAL_MATCH_RESULT_NONE,
  MODAL_MATCH_RETRY,
  MODAL_MATCH_RUNNING,
  MODAL_MATCH_THIS_PHOTO,
  MODAL_MATCH_VIEW_RESULTS,
  MODAL_TITLE_IMAGE_DETAILS,
  MODAL_VIEW_ON_INSTAGRAM,
  MSG_CLICK_FOR_DETAILS,
  MSG_ERROR_PREFIX,
  MSG_PAGE_OF,
  MSG_SHOWING_RANGE,
  PAGINATION_NEXT,
  PAGINATION_PREVIOUS,
} from "../constants/strings";
import { useModal } from "../hooks/useModal";
import type { InstagramImage, Job } from "../services/api";
import { ImagesAPI, JobsAPI } from "../services/api";
import { useMatchOptions } from "../stores/matchOptionsContext";

export function InstagramPage() {
  const [images, setImages] = useState<InstagramImage[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
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

  // Fetch images with given offset and filter
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
        setOffset(newOffset);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setIsLoading(false);
      }
    },
    [dateFilter],
  );

  // Initial load - fetch months and first page
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

  const handlePrevPage = () => {
    if (offset > 0) {
      fetchImages(Math.max(0, offset - ITEMS_PER_PAGE), dateFilter);
    }
  };

  const handleNextPage = () => {
    if (pagination.has_more) {
      fetchImages(offset + ITEMS_PER_PAGE, dateFilter);
    }
  };

  const handleDateFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newFilter = e.target.value;
    setDateFilter(newFilter);
    setOffset(0);
    fetchImages(0, newFilter);
  };

  const clearDateFilter = () => {
    setDateFilter("");
    setOffset(0);
    fetchImages(0, "");
  };

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">
          {MSG_ERROR_PREFIX} {error}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
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

      {/* Grid */}
      {isLoading && images.length === 0 ? (
        <LoadingGrid />
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

          {pagination.total_pages > 1 && (
            <Pagination
              pagination={pagination}
              total={total}
              offset={offset}
              onPrev={handlePrevPage}
              onNext={handleNextPage}
              isLoading={isLoading}
            />
          )}
        </>
      )}

      {isModalOpen && selectedImage && (
        <ImageDetailsModal image={selectedImage} onClose={closeModal} />
      )}
    </div>
  );
}

// Extracted sub-components...

function LoadingGrid() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <ImageSkeleton key={i} />
      ))}
    </div>
  );
}

function ImageSkeleton() {
  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      <div className="aspect-square bg-gray-200 animate-pulse" />
      <div className="p-2 space-y-1">
        <div className="h-3 bg-gray-200 rounded animate-pulse" />
        <div className="h-2 bg-gray-200 rounded w-2/3 animate-pulse" />
      </div>
    </div>
  );
}

function Pagination({
  pagination,
  total,
  offset,
  onPrev,
  onNext,
  isLoading,
}: {
  pagination: { current_page: number; total_pages: number; has_more: boolean };
  total: number;
  offset: number;
  onPrev: () => void;
  onNext: () => void;
  isLoading: boolean;
}) {
  return (
    <div className="flex items-center justify-between pt-6 border-t border-gray-200">
      <button
        onClick={onPrev}
        disabled={offset === 0 || isLoading}
        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {PAGINATION_PREVIOUS}
      </button>

      <div className="text-sm text-gray-600">
        {MSG_PAGE_OF.replace(
          "{current}",
          String(pagination.current_page),
        ).replace("{total}", String(pagination.total_pages))}
        <span className="text-gray-400 mx-2">|</span>
        {MSG_SHOWING_RANGE.replace("{start}", String(offset + 1))
          .replace("{end}", String(Math.min(offset + ITEMS_PER_PAGE, total)))
          .replace("{total}", String(total))}
      </div>

      <button
        onClick={onNext}
        disabled={!pagination.has_more || isLoading}
        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {PAGINATION_NEXT}
      </button>
    </div>
  );
}

function InstagramImageCard({
  image,
  onClick,
}: {
  image: InstagramImage;
  onClick: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`;

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group bg-white cursor-pointer"
      onClick={onClick}
    >
      <div className="aspect-square bg-gray-100 relative">
        {!loaded && !error && (
          <div className="absolute inset-0 bg-gray-200 animate-pulse" />
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <span className="text-xs text-gray-400">Error</span>
          </div>
        )}
        <img
          src={thumbnailUrl}
          alt={image.filename}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
        {image.total_in_post > 1 && (
          <div className="absolute top-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            {image.image_index}/{image.total_in_post}
          </div>
        )}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white text-sm font-medium">
            {MSG_CLICK_FOR_DETAILS}
          </span>
        </div>
      </div>
      <div className="p-2">
        <div className="flex items-start justify-between gap-1">
          <div className="flex flex-col min-w-0">
            <p
              className="text-xs font-medium text-gray-900 truncate"
              title={image.instagram_folder}
            >
              {image.instagram_folder}
            </p>
            <p
              className="text-[10px] text-gray-500 uppercase truncate"
              title={image.source_folder}
            >
              {image.source_folder}
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(image.crawled_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}

function ImageDetailsModal({
  image,
  onClose,
}: {
  image: InstagramImage;
  onClose: () => void;
}) {
  const thumbnailUrl = `/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`;
  const { options: matchOptions, updateOption, resetOptions, availableModels, weightsError } =
    useMatchOptions();
  const [matchState, setMatchState] = useState<"idle" | "running" | "done">("idle");
  const [matchJob, setMatchJob] = useState<Job | null>(null);
  const [matchResult, setMatchResult] = useState<{ matched: number; score?: number } | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    setMatchState("idle");
    setMatchJob(null);
    setMatchResult(null);
    setAdvancedOpen(false);
    clearPoll();
    return clearPoll;
  }, [image.key]);

  const pollJob = (jobId: string) => {
    clearPoll();
    pollIntervalRef.current = setInterval(async () => {
      try {
        const job = await JobsAPI.get(jobId);
        setMatchJob(job);
        if (job.status === "completed" || job.status === "failed") {
          clearPoll();
          setMatchState("done");
          if (job.result) {
            setMatchResult({
              matched: job.result.matched ?? 0,
              score: job.result.best_score,
            });
          }
        }
      } catch {
        clearPoll();
        setMatchState("done");
      }
    }, 2000);
  };

  const startSingleMatch = async () => {
    setMatchState("running");
    setMatchResult(null);
    try {
      const job = await JobsAPI.create("vision_match", {
        media_key: image.key,
        vision_model: matchOptions.selectedModel,
        threshold: matchOptions.threshold,
        weights: {
          phash: matchOptions.phashWeight,
          description: matchOptions.descWeight,
          vision: matchOptions.visionWeight,
        },
      });
      setMatchJob(job);
      pollJob(job.id);
    } catch (err) {
      setMatchState("idle");
      console.error("Failed to start match:", err);
    }
  };

  return (
    <Modal onClose={onClose}>
      <ModalHeader title={MODAL_TITLE_IMAGE_DETAILS} onClose={onClose} />

      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Image Preview */}
          <div className="space-y-4">
            <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={thumbnailUrl}
                alt={image.filename}
                className="w-full h-full object-contain"
              />
            </div>

            <div className="space-y-3">
              {image.post_url && (
                <a
                  href={image.post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full bg-blue-600 text-white text-center py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
                >
                  {MODAL_VIEW_ON_INSTAGRAM}
                </a>
              )}

              {matchState === "idle" && (
                <button
                  type="button"
                  onClick={startSingleMatch}
                  className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 transition-colors text-sm font-medium"
                >
                  {MODAL_MATCH_THIS_PHOTO}
                </button>
              )}

              {matchState === "running" && (
                <div className="flex items-center gap-2 py-2 px-4 bg-purple-50 rounded-md text-sm text-purple-700">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  {MODAL_MATCH_RUNNING}
                  {matchJob && ` ${matchJob.progress}%`}
                </div>
              )}

              {matchState === "done" && matchResult && (
                <div
                  className={`py-2 px-4 rounded-md text-sm ${matchResult.matched > 0 ? "bg-green-50 text-green-700" : "bg-gray-50 text-gray-600"}`}
                >
                  <p className="font-medium">
                    {matchResult.matched > 0 ? MODAL_MATCH_RESULT_FOUND : MODAL_MATCH_RESULT_NONE}
                    {matchResult.score != null && ` (score: ${matchResult.score.toFixed(2)})`}
                  </p>
                  <div className="flex gap-2 mt-2">
                    {matchResult.matched > 0 && (
                      <a href="/matching" className="text-xs text-blue-600 hover:underline">
                        {MODAL_MATCH_VIEW_RESULTS}
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => setMatchState("idle")}
                      className="text-xs text-purple-600 hover:underline"
                    >
                      {MODAL_MATCH_RETRY}
                    </button>
                  </div>
                </div>
              )}

              {matchState === "done" && matchJob?.status === "failed" && (
                <div className="py-2 px-4 rounded-md text-sm bg-red-50 text-red-700">
                  <p className="font-medium">
                    Match failed: {matchJob.error || "Unknown error"}
                  </p>
                  <button
                    type="button"
                    onClick={() => setMatchState("idle")}
                    className="text-xs text-purple-600 hover:underline mt-1"
                  >
                    {MODAL_MATCH_RETRY}
                  </button>
                </div>
              )}

              <AdvancedOptions
                isOpen={advancedOpen}
                onToggle={() => setAdvancedOpen(!advancedOpen)}
                availableModels={availableModels}
                selectedModel={matchOptions.selectedModel}
                onModelChange={(model) => updateOption("selectedModel", model)}
                threshold={matchOptions.threshold}
                onThresholdChange={(v) => updateOption("threshold", v)}
                phashWeight={matchOptions.phashWeight}
                onPhashWeightChange={(v) => updateOption("phashWeight", v)}
                descWeight={matchOptions.descWeight}
                onDescWeightChange={(v) => updateOption("descWeight", v)}
                visionWeight={matchOptions.visionWeight}
                onVisionWeightChange={(v) => updateOption("visionWeight", v)}
                weightsError={weightsError}
                onReset={resetOptions}
              />
            </div>
          </div>

          {/* Metadata */}
          <div className="space-y-4">
            <MetadataSection title={META_SECTION_BASIC_INFO}>
              <div className="space-y-2">
                <MetadataRow label={LABEL_FILENAME} value={image.filename} />
                <MetadataRow label={LABEL_MEDIA_KEY} value={image.key} />
                <MetadataRow
                  label={LABEL_SOURCE_FOLDER}
                  value={image.source_folder}
                />
                <MetadataRow
                  label={LABEL_DATE_FOLDER}
                  value={image.instagram_folder}
                />
                <MetadataRow
                  label={LABEL_ADDED}
                  value={new Date(image.crawled_at).toLocaleString()}
                />
              </div>
            </MetadataSection>

            {image.image_hash && (
              <MetadataSection title={META_SECTION_IMAGE_ANALYSIS}>
                <MetadataRow
                  label={LABEL_VISUAL_HASH}
                  value={image.image_hash}
                  monospace
                />
                <p className="text-xs text-gray-500 mt-2">{HASH_EXPLANATION}</p>
              </MetadataSection>
            )}

            <ExifDataSection exifData={image.exif_data} />

            {image.description && (
              <MetadataSection title={META_SECTION_CAPTION}>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">
                  {image.description}
                </p>
              </MetadataSection>
            )}

            <MetadataSection title={META_SECTION_FILE_LOCATION}>
              <code className="text-xs text-gray-600 break-all">
                {image.local_path}
              </code>
            </MetadataSection>
          </div>
        </div>
      </div>

      <ModalFooter>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
        >
          {MODAL_CLOSE}
        </button>
      </ModalFooter>
    </Modal>
  );
}

function formatMonth(yyyymm: string): string {
  if (yyyymm.length !== 6) return yyyymm;

  const year = yyyymm.substring(0, 4);
  const month = yyyymm.substring(4, 6);

  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString("en-US", { year: "numeric", month: "long" });
}
