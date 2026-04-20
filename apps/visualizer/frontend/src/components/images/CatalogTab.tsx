import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ImagesAPI, PerspectivesAPI, type CatalogImage } from '../../services/api';
import { ImageDetailModal, ImageTile, fromCatalogListRow } from '../image-view';
import { Pagination } from '../ui/Pagination';
import {
  FILTER_ALL_DATES,
  CATALOG_FILTER_LABEL_STATUS,
  CATALOG_FILTER_LABEL_ANALYZED,
  CATALOG_FILTER_LABEL_MONTH,
  CATALOG_FILTER_LABEL_KEYWORD,
  CATALOG_FILTER_LABEL_MIN_RATING,
  CATALOG_FILTER_LABEL_DATE_RANGE,
  CATALOG_FILTER_LABEL_COLOR,
  CATALOG_FILTER_LABEL_SCORE_PERSPECTIVE,
  CATALOG_FILTER_LABEL_MIN_SCORE,
  CATALOG_FILTER_LABEL_SORT_SCORE,
  CATALOG_FILTER_POSTED_ALL,
  CATALOG_FILTER_POSTED,
  CATALOG_FILTER_NOT_POSTED,
  CATALOG_FILTER_ANALYZED_ALL,
  CATALOG_FILTER_ANALYZED_ONLY,
  CATALOG_FILTER_NOT_ANALYZED,
  CATALOG_FILTER_MIN_RATING_ANY,
  CATALOG_FILTER_SCORE_ANY,
  CATALOG_FILTER_SORT_NONE,
  CATALOG_FILTER_SORT_HIGH_LOW,
  CATALOG_FILTER_SORT_LOW_HIGH,
  CATALOG_FILTER_KEYWORD_PLACEHOLDER,
  CATALOG_FILTER_KEYWORD_ARIA,
  CATALOG_FILTER_COLOR_PLACEHOLDER,
  CATALOG_FILTER_COLOR_ARIA,
} from '../../constants/strings';
import { formatMonth } from '../../utils/date';
import { useFilters } from '../../hooks/useFilters';
import { FilterBar } from '../filters/FilterBar';
import type { FilterSchema } from '../filters/types';

const LIMIT = 50;

/** Row-data we need to open the consolidated modal — only type + key are
 *  required (detail endpoint fills the rest); the full row is kept so the
 *  header can render instantly while the detail request is in flight. */
type SelectedCatalogEntry = {
  key: string;
  initial?: CatalogImage;
};

type CatalogTabProps = {
  /** Fires when the posted / not-posted filter changes (for parent UI, e.g. Analytics cross-link). */
  onPostedFilterChange?: (posted: boolean | undefined) => void;
};

const postedSerialize = (value: unknown): string => {
  if (value === undefined) return 'all';
  return value === true ? 'posted' : 'not-posted';
};
const postedDeserialize = (raw: string): unknown => {
  if (raw === 'posted') return true;
  if (raw === 'not-posted') return false;
  return undefined;
};

const analyzedSerialize = (value: unknown): string => {
  if (value === undefined) return 'all';
  return value === true ? 'analyzed' : 'not_analyzed';
};
const analyzedDeserialize = (raw: string): unknown => {
  if (raw === 'analyzed') return true;
  if (raw === 'not_analyzed') return false;
  return undefined;
};

const formatPostedChip = (value: unknown): string => {
  if (value === true) return CATALOG_FILTER_POSTED;
  if (value === false) return CATALOG_FILTER_NOT_POSTED;
  return CATALOG_FILTER_POSTED_ALL;
};

const formatAnalyzedChip = (value: unknown): string => {
  if (value === true) return CATALOG_FILTER_ANALYZED_ONLY;
  if (value === false) return CATALOG_FILTER_NOT_ANALYZED;
  return CATALOG_FILTER_ANALYZED_ALL;
};

const formatMinRatingChip = (value: unknown): string => {
  if (value === '' || value === undefined || value === null) return CATALOG_FILTER_MIN_RATING_ANY;
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return '★'.repeat(n);
};

const formatDateRangeChip = (value: unknown): string => {
  if (!value || typeof value !== 'object') return '';
  const v = value as { from?: string; to?: string };
  const from = typeof v.from === 'string' ? v.from : '';
  const to = typeof v.to === 'string' ? v.to : '';
  if (from && to) return `${from} → ${to}`;
  if (from) return `from ${from}`;
  if (to) return `to ${to}`;
  return '';
};

const formatSortChip = (value: unknown): string => {
  if (value === 'desc') return CATALOG_FILTER_SORT_HIGH_LOW;
  if (value === 'asc') return CATALOG_FILTER_SORT_LOW_HIGH;
  return CATALOG_FILTER_SORT_NONE;
};

export function CatalogTab({ onPostedFilterChange }: CatalogTabProps = {}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [images, setImages] = useState<CatalogImage[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [initialLoad, setInitialLoad] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [catalogFetchSucceeded, setCatalogFetchSucceeded] = useState(false);
  const [selected, setSelected] = useState<SelectedCatalogEntry | null>(null);
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const [scorePerspectives, setScorePerspectives] = useState<
    { slug: string; display_name: string }[]
  >([]);

  const catalogSchema = useMemo<FilterSchema>(() => {
    return [
      {
        type: 'toggle',
        key: 'posted',
        label: CATALOG_FILTER_LABEL_STATUS,
        options: [
          { value: 'all', label: CATALOG_FILTER_POSTED_ALL },
          { value: 'posted', label: CATALOG_FILTER_POSTED },
          { value: 'not-posted', label: CATALOG_FILTER_NOT_POSTED },
        ],
        serialize: postedSerialize,
        deserialize: postedDeserialize,
        formatValue: formatPostedChip,
      },
      {
        type: 'toggle',
        key: 'analyzed',
        label: CATALOG_FILTER_LABEL_ANALYZED,
        options: [
          { value: 'all', label: CATALOG_FILTER_ANALYZED_ALL },
          { value: 'analyzed', label: CATALOG_FILTER_ANALYZED_ONLY },
          { value: 'not_analyzed', label: CATALOG_FILTER_NOT_ANALYZED },
        ],
        serialize: analyzedSerialize,
        deserialize: analyzedDeserialize,
        formatValue: formatAnalyzedChip,
      },
      ...(availableMonths.length > 0
        ? ([
            {
              type: 'select',
              key: 'month',
              label: CATALOG_FILTER_LABEL_MONTH,
              options: [
                { value: '', label: FILTER_ALL_DATES },
                ...availableMonths.map((m) => ({ value: m, label: formatMonth(m) })),
              ],
              formatValue: (v: unknown) =>
                typeof v === 'string' && v !== '' ? formatMonth(v) : FILTER_ALL_DATES,
            },
          ] as FilterSchema)
        : []),
      {
        type: 'search',
        key: 'keyword',
        label: CATALOG_FILTER_LABEL_KEYWORD,
        debounceMs: 350,
        placeholder: CATALOG_FILTER_KEYWORD_PLACEHOLDER,
        ariaLabel: CATALOG_FILTER_KEYWORD_ARIA,
        className: 'h-9 min-w-[8rem] w-36',
      },
      {
        type: 'select',
        key: 'minRating',
        label: CATALOG_FILTER_LABEL_MIN_RATING,
        paramName: 'min_rating',
        numberValue: true,
        options: [
          { value: '', label: CATALOG_FILTER_MIN_RATING_ANY },
          ...[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: '★'.repeat(n) })),
        ],
        formatValue: formatMinRatingChip,
      },
      {
        type: 'dateRange',
        key: 'dateRange',
        label: CATALOG_FILTER_LABEL_DATE_RANGE,
        chipLabel: CATALOG_FILTER_LABEL_DATE_RANGE,
        formatValue: formatDateRangeChip,
      },
      {
        type: 'search',
        key: 'colorLabel',
        label: CATALOG_FILTER_LABEL_COLOR,
        paramName: 'color_label',
        debounceMs: 350,
        placeholder: CATALOG_FILTER_COLOR_PLACEHOLDER,
        ariaLabel: CATALOG_FILTER_COLOR_ARIA,
        className: 'h-9 min-w-[6rem] w-28',
      },
      {
        type: 'select',
        key: 'scorePerspective',
        label: CATALOG_FILTER_LABEL_SCORE_PERSPECTIVE,
        className: 'min-w-[8rem]',
        options: [
          { value: '', label: CATALOG_FILTER_SCORE_ANY },
          ...scorePerspectives.map((p) => ({ value: p.slug, label: p.display_name })),
        ],
        formatValue: (v) => {
          if (!v) return CATALOG_FILTER_SCORE_ANY;
          const match = scorePerspectives.find((p) => p.slug === v);
          return match ? match.display_name : String(v);
        },
      },
      {
        type: 'select',
        key: 'minCatalogScore',
        label: CATALOG_FILTER_LABEL_MIN_SCORE,
        paramName: 'min_score',
        numberValue: true,
        options: [
          { value: '', label: CATALOG_FILTER_SCORE_ANY },
          ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => ({
            value: String(n),
            label: `${n}+`,
          })),
        ],
        enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
        formatValue: (v) =>
          v === '' || v === undefined || v === null ? CATALOG_FILTER_SCORE_ANY : `${v}+`,
      },
      {
        type: 'select',
        key: 'sortByScore',
        label: CATALOG_FILTER_LABEL_SORT_SCORE,
        paramName: 'sort_by_score',
        defaultValue: 'none',
        options: [
          { value: 'none', label: CATALOG_FILTER_SORT_NONE },
          { value: 'desc', label: CATALOG_FILTER_SORT_HIGH_LOW },
          { value: 'asc', label: CATALOG_FILTER_SORT_LOW_HIGH },
        ],
        enabledBy: { filterKey: 'scorePerspective', when: (v) => Boolean(v) },
        toParam: (v) => (v === 'none' || v === '' || v === undefined ? undefined : v),
        formatValue: formatSortChip,
      },
    ];
  }, [availableMonths, scorePerspectives]);

  const filters = useFilters(catalogSchema);
  const { values: filterValues, rawValues: filterRawValues, toQueryParams, activeCount } = filters;

  const fetchId = useRef(0);

  const loadImages = useCallback(async () => {
    const id = ++fetchId.current;
    try {
      setFetching(true);
      setLoadError(null);
      const offset = (page - 1) * LIMIT;
      const data = await ImagesAPI.listCatalog({
        ...toQueryParams(),
        limit: LIMIT,
        offset,
      });
      if (id !== fetchId.current) return;
      setImages(data.images);
      setTotal(data.total);
      setCatalogFetchSucceeded(true);
    } catch (err) {
      if (id !== fetchId.current) return;
      console.error('Failed to load catalog images:', err);
      const message = err instanceof Error ? err.message : 'Failed to load catalog images';
      setLoadError(message);
      setImages([]);
      setTotal(0);
    } finally {
      if (id === fetchId.current) {
        setFetching(false);
        setInitialLoad(false);
      }
    }
  }, [page, toQueryParams]);

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
    PerspectivesAPI.list({ active_only: true })
      .then((rows) => {
        const sorted = [...rows].sort((a, b) => a.slug.localeCompare(b.slug));
        setScorePerspectives(sorted.map((r) => ({ slug: r.slug, display_name: r.display_name })));
      })
      .catch((err) => console.error('Failed to load perspectives:', err));
  }, []);

  useEffect(() => {
    loadImages();
  }, [loadImages]);

  useEffect(() => {
    const sp = new URLSearchParams(location.search);
    const raw = sp.get('image_key');
    if (!raw) return;
    setSelected({ key: raw });
    sp.delete('image_key');
    const next = sp.toString();
    navigate({ pathname: location.pathname, search: next ? `?${next}` : '' }, { replace: true });
  }, [location.search, location.pathname, navigate]);

  const postedCommitted = filterValues.posted as boolean | undefined;
  useEffect(() => {
    onPostedFilterChange?.(postedCommitted);
  }, [postedCommitted, onPostedFilterChange]);

  const dateRangeValue = filterValues.dateRange as { from?: string; to?: string } | undefined;
  const dateRangeFrom = dateRangeValue?.from ?? '';
  const dateRangeTo = dateRangeValue?.to ?? '';

  // D-10: non-search filter changes reset page to 1 immediately.
  useEffect(() => {
    setPage(1);
  }, [
    filterValues.posted,
    filterValues.analyzed,
    filterValues.month,
    filterValues.minRating,
    dateRangeFrom,
    dateRangeTo,
    filterValues.scorePerspective,
    filterValues.minCatalogScore,
    filterValues.sortByScore,
  ]);

  // Debounced text parity with legacy lines 255–264: reset page on committed keyword / colorLabel change.
  const prevKeyword = useRef(filterValues.keyword);
  const prevColor = useRef(filterValues.colorLabel);
  useEffect(() => {
    if (
      prevKeyword.current !== filterValues.keyword ||
      prevColor.current !== filterValues.colorLabel
    ) {
      prevKeyword.current = filterValues.keyword;
      prevColor.current = filterValues.colorLabel;
      setPage(1);
    }
  }, [filterValues.keyword, filterValues.colorLabel]);

  const hasActiveFilters = activeCount > 0;
  const loading = initialLoad;

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

  // Silence unused-var warning for rawValues destructure — kept for future debug / UAT.
  void filterRawValues;

  return (
    <div className="space-y-6">
      <FilterBar
        schema={catalogSchema}
        filters={filters}
        summary={<p className="text-sm text-text-secondary">{summaryText}</p>}
        disabled={loading}
      />

      {loading ? (
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
          <svg
            className="mx-auto h-12 w-12 text-text-tertiary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-text">No Catalog Images</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Your catalog database is empty or not yet indexed.
          </p>
        </div>
      ) : total === 0 && hasActiveFilters ? (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-text-tertiary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-text">No Images Found</h3>
          <p className="mt-1 text-sm text-text-secondary">Try changing or clearing the filters.</p>
        </div>
      ) : (
        <>
          <div
            className={`relative transition-opacity duration-150 ${
              fetching ? 'opacity-50 pointer-events-none' : ''
            }`}
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {images.map((image) => (
                <ImageTile
                  key={image.id != null ? String(image.id) : image.key}
                  image={fromCatalogListRow(image)}
                  variant="grid"
                  primaryScoreSource="catalog"
                  onClick={() => setSelected({ key: image.key, initial: image })}
                />
              ))}
            </div>
          </div>

          {totalPages > 1 && (
            <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
          )}
        </>
      )}

      {selected && (
        <ImageDetailModal
          imageType="catalog"
          imageKey={selected.key}
          initialImage={selected.initial ? fromCatalogListRow(selected.initial) : undefined}
          primaryScoreSource="catalog"
          scorePerspectiveSlug={
            typeof filterValues.scorePerspective === 'string' && filterValues.scorePerspective
              ? filterValues.scorePerspective
              : undefined
          }
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
