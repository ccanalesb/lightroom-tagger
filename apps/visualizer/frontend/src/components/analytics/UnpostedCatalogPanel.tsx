import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AnalyticsAPI,
  ImagesAPI,
  type UnpostedCatalogItem,
} from '../../services/api'
import { ImageDetailModal, ImageTile, fromUnpostedRow } from '../image-view'
import { Card, CardContent } from '../ui/Card'
import { Pagination } from '../ui/Pagination'
import { TileGrid } from '../ui/TileGrid'
import { formatMonth } from '../../utils/date'
import {
  ANALYTICS_APPLY,
  ANALYTICS_NOT_POSTED_EMPTY_ALL_POSTED,
  ANALYTICS_NOT_POSTED_EMPTY_NO_MATCH,
  ANALYTICS_NOT_POSTED_FROM_DATE,
  ANALYTICS_NOT_POSTED_HELP,
  ANALYTICS_NOT_POSTED_MIN_RATING,
  ANALYTICS_NOT_POSTED_MONTH,
  ANALYTICS_NOT_POSTED_TITLE,
  ANALYTICS_NOT_POSTED_TO_DATE,
  FILTER_ALL_DATES,
  MSG_LOADING,
  MSG_SHOWING_RANGE,
} from '../../constants/strings'

const PAGE_SIZE = 50

type AppliedUnpostedFilters = {
  dateFrom: string
  dateTo: string
  minRating: number | ''
  month: string
}

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function formatShowingRange(start: number, end: number, total: number): string {
  return MSG_SHOWING_RANGE.replace('{start}', String(start))
    .replace('{end}', String(end))
    .replace('{total}', String(total))
}

export function UnpostedCatalogPanel() {
  const initialApplied = useMemo<AppliedUnpostedFilters>(
    () => ({ dateFrom: '', dateTo: '', minRating: '', month: '' }),
    [],
  )

  const [dateFromDraft, setDateFromDraft] = useState(initialApplied.dateFrom)
  const [dateToDraft, setDateToDraft] = useState(initialApplied.dateTo)
  const [minRatingDraft, setMinRatingDraft] = useState<number | ''>(initialApplied.minRating)
  const [monthDraft, setMonthDraft] = useState(initialApplied.month)

  const [applied, setApplied] = useState<AppliedUnpostedFilters>(initialApplied)
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState<UnpostedCatalogItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<UnpostedCatalogItem | null>(null)

  const [availableMonths, setAvailableMonths] = useState<string[]>([])

  useEffect(() => {
    ImagesAPI.getCatalogMonths()
      .then((data) => setAvailableMonths(data.months))
      .catch(() => {})
  }, [])

  const load = useCallback(async () => {
    if (applied.dateFrom && applied.dateTo && applied.dateFrom > applied.dateTo) {
      setError('Start date must be on or before end date.')
      setRows([])
      setTotal(0)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    const offset = (page - 1) * PAGE_SIZE
    try {
      const data = await AnalyticsAPI.getUnpostedCatalog({
        ...(applied.dateFrom ? { date_from: applied.dateFrom } : {}),
        ...(applied.dateTo ? { date_to: applied.dateTo } : {}),
        ...(applied.minRating !== '' ? { min_rating: applied.minRating } : {}),
        ...(applied.month ? { month: applied.month } : {}),
        limit: PAGE_SIZE,
        offset,
      })
      setRows(data.images)
      setTotal(data.total)
    } catch (e) {
      setError(errMessage(e))
      setRows([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [applied, page])

  useEffect(() => {
    void load()
  }, [load])

  const handleApply = () => {
    setApplied({
      dateFrom: dateFromDraft,
      dateTo: dateToDraft,
      minRating: minRatingDraft,
      month: monthDraft,
    })
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const rangeLabel = useMemo(() => {
    if (total === 0) return null
    const start = (page - 1) * PAGE_SIZE + 1
    const end = Math.min(page * PAGE_SIZE, total)
    return formatShowingRange(start, end, total)
  }, [page, total])

  const emptyMessage =
    total === 0 && !error
      ? applied.dateFrom || applied.dateTo || applied.minRating !== '' || applied.month
        ? ANALYTICS_NOT_POSTED_EMPTY_NO_MATCH
        : ANALYTICS_NOT_POSTED_EMPTY_ALL_POSTED
      : null

  return (
    <section className="space-y-3" aria-labelledby="analytics-unposted-heading">
      <h2 id="analytics-unposted-heading" className="text-card-title text-text">
        {ANALYTICS_NOT_POSTED_TITLE}
      </h2>
      <Card padding="md">
        <CardContent className="space-y-6 !text-text">
          <p className="text-sm text-text-secondary">{ANALYTICS_NOT_POSTED_HELP}</p>
          <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="unposted-date-from" className="text-sm font-medium text-text">
                {ANALYTICS_NOT_POSTED_FROM_DATE}
              </label>
              <input
                id="unposted-date-from"
                type="date"
                value={dateFromDraft}
                onChange={(e) => setDateFromDraft(e.target.value)}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="unposted-date-to" className="text-sm font-medium text-text">
                {ANALYTICS_NOT_POSTED_TO_DATE}
              </label>
              <input
                id="unposted-date-to"
                type="date"
                value={dateToDraft}
                onChange={(e) => setDateToDraft(e.target.value)}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="unposted-min-rating" className="text-sm font-medium text-text">
                {ANALYTICS_NOT_POSTED_MIN_RATING}
              </label>
              <select
                id="unposted-min-rating"
                value={minRatingDraft === '' ? '' : String(minRatingDraft)}
                onChange={(e) => {
                  const v = e.target.value
                  setMinRatingDraft(v === '' ? '' : Number(v))
                }}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <option value="">Any</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {'★'.repeat(n)}
                  </option>
                ))}
              </select>
            </div>
            {availableMonths.length > 0 ? (
              <div className="flex min-w-[10rem] flex-col gap-1">
                <label htmlFor="unposted-month" className="text-sm font-medium text-text">
                  {ANALYTICS_NOT_POSTED_MONTH}
                </label>
                <select
                  id="unposted-month"
                  value={monthDraft}
                  onChange={(e) => setMonthDraft(e.target.value)}
                  className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <option value="">{FILTER_ALL_DATES}</option>
                  {availableMonths.map((m) => (
                    <option key={m} value={m}>
                      {formatMonth(m)}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            <button
              type="button"
              onClick={handleApply}
              className="rounded-base bg-accent px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg"
            >
              {ANALYTICS_APPLY}
            </button>
          </div>

          {loading ? (
            <p className="text-sm text-text-secondary" role="status" aria-live="polite">
              {MSG_LOADING}
            </p>
          ) : null}

          {error ? (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          ) : null}

          {!loading && !error && rangeLabel ? (
            <p className="text-sm text-text-secondary">{rangeLabel}</p>
          ) : null}

          {!loading && !error && emptyMessage ? (
            <p className="text-sm text-text-secondary" role="status">
              {emptyMessage}
            </p>
          ) : null}

          {!loading && !error && rows.length > 0 ? (
            <>
              <TileGrid>
                {rows.map((row) => (
                  <ImageTile
                    key={row.key}
                    image={fromUnpostedRow(row)}
                    variant="grid"
                    primaryScoreSource="identity"
                    onClick={() => setSelected(row)}
                  />
                ))}
              </TileGrid>
              {totalPages > 1 ? (
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                  disabled={loading}
                />
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      {selected ? (
        <ImageDetailModal
          imageType="catalog"
          imageKey={selected.key}
          initialImage={fromUnpostedRow(selected)}
          primaryScoreSource="identity"
          onClose={() => setSelected(null)}
        />
      ) : null}
    </section>
  )
}
