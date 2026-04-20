import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  IdentityAPI,
  type PostNextCandidate,
  type PostNextSuggestionsMeta,
} from '../../services/api'
import { ImageDetailModal, fromPostNextRow } from '../image-view'
import { Button } from '../ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  IDENTITY_ACTION_OPEN_CATALOG,
  IDENTITY_POST_NEXT_EMPTY_FALLBACK,
  IDENTITY_POST_NEXT_HELP,
  IDENTITY_REASON_CODE_LABELS,
  IDENTITY_SECTION_POST_NEXT,
  MSG_LOADING,
  FILTER_LABEL_SORT_DATE,
  FILTER_SORT_DATE_NEWEST,
  FILTER_SORT_DATE_OLDEST,
  FILTER_SORT_DATE_NONE,
  msgShowingOf,
} from '../../constants/strings'
import { FilterBar } from '../filters/FilterBar'
import { useFilters } from '../../hooks/useFilters'
import type { FilterSchema } from '../filters/types'

const SUGGESTIONS_LIMIT = 20

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function labelForReasonCode(code: string): string {
  return IDENTITY_REASON_CODE_LABELS[code] ?? code.replace(/_/g, ' ')
}

export function PostNextSuggestionsPanel() {
  const [rows, setRows] = useState<PostNextCandidate[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)
  const [meta, setMeta] = useState<PostNextSuggestionsMeta | null>(null)
  const [emptyState, setEmptyState] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<PostNextCandidate | null>(null)

  const postNextSchema = useMemo<FilterSchema>(
    () => [
      {
        type: 'select',
        key: 'sortByDate',
        label: FILTER_LABEL_SORT_DATE,
        paramName: 'sort_by_date',
        defaultValue: 'none',
        options: [
          { value: 'none', label: FILTER_SORT_DATE_NONE },
          { value: 'newest', label: FILTER_SORT_DATE_NEWEST },
          { value: 'oldest', label: FILTER_SORT_DATE_OLDEST },
        ],
        toParam: (v) => (v === 'none' || v === '' || v === undefined ? undefined : v),
      },
    ],
    [],
  )
  const filters = useFilters(postNextSchema)
  const sortByDate = filters.values.sortByDate as string | undefined
  const sortParam =
    sortByDate && sortByDate !== 'none'
      ? (sortByDate as 'newest' | 'oldest')
      : undefined

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setOffset(0)
    IdentityAPI.getSuggestions({
      limit: SUGGESTIONS_LIMIT,
      offset: 0,
      sort_by_date: sortParam,
    })
      .then((res) => {
        if (cancelled) return
        setRows(res.candidates)
        setTotal(res.total)
        setOffset(res.candidates.length)
        setMeta(res.meta)
        setEmptyState(res.empty_state)
      })
      .catch((e) => {
        if (cancelled) return
        setError(errMessage(e))
        setRows([])
        setTotal(null)
        setOffset(0)
        setMeta(null)
        setEmptyState(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sortParam])

  const handleLoadMore = () => {
    if (total === null || offset >= total || loadingMore) return
    setLoadingMore(true)
    const cur = rows
    IdentityAPI.getSuggestions({
      limit: SUGGESTIONS_LIMIT,
      offset: offset,
      sort_by_date: sortParam,
    })
      .then((res) => {
        const seen = new Set(cur.map((r) => r.image_key))
        const extra = res.candidates.filter((c) => !seen.has(c.image_key))
        const next = [...cur, ...extra]
        setRows(next)
        setTotal(res.total)
        setOffset(next.length)
        setMeta(res.meta)
        setEmptyState(res.empty_state)
      })
      .catch((e) => {
        setError(errMessage(e))
      })
      .finally(() => {
        setLoadingMore(false)
      })
  }

  const emptyMessage =
    !loading && !error && rows.length === 0
      ? emptyState ?? IDENTITY_POST_NEXT_EMPTY_FALLBACK
      : null

  return (
    <section className="space-y-3" aria-labelledby="identity-post-next-heading">
      <h2 id="identity-post-next-heading" className="text-card-title text-text">
        {IDENTITY_SECTION_POST_NEXT}
      </h2>
      <Card padding="md">
        <CardHeader>
          <CardTitle className="text-base sr-only">{IDENTITY_SECTION_POST_NEXT}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 !text-text">
          <p className="text-sm text-text-secondary">{IDENTITY_POST_NEXT_HELP}</p>
          <FilterBar
            schema={postNextSchema}
            filters={filters}
            summary={
              !loading && !error && rows.length > 0 && total !== null ? (
                <p className="text-sm text-text-secondary">
                  {msgShowingOf(rows.length, total, 'suggestions')}
                </p>
              ) : null
            }
            disabled={loading}
          />

          {meta?.cadence_note ? (
            <p
              className="rounded-base border border-border bg-surface px-3 py-2 text-sm text-text-secondary"
              role="status"
            >
              {meta.cadence_note}
            </p>
          ) : null}

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

          {!loading && !error && emptyMessage ? (
            <p className="text-sm text-text-secondary" role="status">
              {emptyMessage}
            </p>
          ) : null}

          {!loading && !error && rows.length > 0 ? (
            <>
              <ol className="space-y-4">
              {rows.map((row, i) => {
                const dateDisplay = row.date_taken
                  ? new Date(row.date_taken).toLocaleDateString()
                  : '—'
                return (
                  <li
                    key={row.image_key}
                    className="flex flex-col gap-3 rounded-card border border-border bg-bg p-3 sm:flex-row sm:items-start"
                  >
                    <button
                      type="button"
                      onClick={() => setSelected(row)}
                      className="mx-auto shrink-0 focus:outline-none focus:ring-2 focus:ring-accent sm:mx-0"
                    >
                      <img
                        src={`/api/images/${row.image_type ?? 'catalog'}/${encodeURIComponent(row.image_key)}/thumbnail`}
                        alt={row.filename}
                        className="h-28 w-28 rounded-base border border-border object-cover"
                        loading="lazy"
                      />
                    </button>
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-xs font-medium text-text-tertiary">#{i + 1}</span>
                        <p className="truncate font-medium text-text">{row.filename}</p>
                        <span className="text-sm font-semibold text-accent">
                          {row.aggregate_score.toFixed(2)}
                        </span>
                        <span className="text-xs text-text-tertiary">{dateDisplay}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {row.reason_codes.map((code, ci) => (
                          <span
                            key={`${code}-${ci}`}
                            className="rounded-full border border-border bg-surface px-2 py-0.5 text-xs text-text-secondary"
                          >
                            {labelForReasonCode(code)}
                          </span>
                        ))}
                      </div>
                      <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
                        {row.reasons.map((r, j) => (
                          <li key={j}>{r}</li>
                        ))}
                      </ul>
                      <Link
                        to={`/images?tab=catalog&image_key=${encodeURIComponent(row.image_key)}`}
                        className="inline-block text-sm font-medium text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent rounded-sm"
                      >
                        {IDENTITY_ACTION_OPEN_CATALOG}
                      </Link>
                    </div>
                  </li>
                )
              })}
              </ol>
              {total !== null && rows.length < total ? (
                <div className="flex justify-center pt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={loadingMore}
                    onClick={handleLoadMore}
                  >
                    Load more
                  </Button>
                </div>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      {selected ? (
        <ImageDetailModal
          imageType={(selected.image_type as 'catalog' | 'instagram') ?? 'catalog'}
          imageKey={selected.image_key}
          initialImage={fromPostNextRow(selected)}
          primaryScoreSource="identity"
          onClose={() => setSelected(null)}
        />
      ) : null}
    </section>
  )
}
