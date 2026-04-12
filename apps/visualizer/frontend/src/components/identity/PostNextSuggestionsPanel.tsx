import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  IdentityAPI,
  type CatalogImage,
  type PostNextCandidate,
  type PostNextSuggestionsMeta,
} from '../../services/api'
import { CatalogImageModal } from '../catalog/CatalogImageModal'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  IDENTITY_ACTION_OPEN_CATALOG,
  IDENTITY_POST_NEXT_EMPTY_FALLBACK,
  IDENTITY_POST_NEXT_HELP,
  IDENTITY_REASON_CODE_LABELS,
  IDENTITY_SECTION_POST_NEXT,
  MSG_LOADING,
} from '../../constants/strings'

const SUGGESTIONS_LIMIT = 20

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function candidateToCatalogStub(row: PostNextCandidate): CatalogImage {
  return {
    id: null,
    key: row.image_key,
    filename: row.filename,
    filepath: '',
    date_taken: row.date_taken,
    rating: typeof row.rating === 'number' ? row.rating : 0,
    pick: false,
    color_label: '',
    keywords: [],
    title: '',
    caption: '',
    copyright: '',
    width: 0,
    height: 0,
    instagram_posted: false,
  }
}

function labelForReasonCode(code: string): string {
  return IDENTITY_REASON_CODE_LABELS[code] ?? code.replace(/_/g, ' ')
}

export function PostNextSuggestionsPanel() {
  const [rows, setRows] = useState<PostNextCandidate[]>([])
  const [meta, setMeta] = useState<PostNextSuggestionsMeta | null>(null)
  const [emptyState, setEmptyState] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<CatalogImage | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    IdentityAPI.getSuggestions({ limit: SUGGESTIONS_LIMIT })
      .then((res) => {
        if (cancelled) return
        setRows(res.candidates)
        setMeta(res.meta)
        setEmptyState(res.empty_state)
      })
      .catch((e) => {
        if (cancelled) return
        setError(errMessage(e))
        setRows([])
        setMeta(null)
        setEmptyState(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

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
                      onClick={() => setSelected(candidateToCatalogStub(row))}
                      className="mx-auto shrink-0 focus:outline-none focus:ring-2 focus:ring-accent sm:mx-0"
                    >
                      <img
                        src={`/api/images/catalog/${encodeURIComponent(row.image_key)}/thumbnail`}
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
          ) : null}
        </CardContent>
      </Card>

      {selected ? (
        <CatalogImageModal image={selected} onClose={() => setSelected(null)} />
      ) : null}
    </section>
  )
}
