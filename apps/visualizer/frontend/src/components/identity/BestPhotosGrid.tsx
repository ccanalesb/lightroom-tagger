import { useCallback, useEffect, useState } from 'react'
import {
  IdentityAPI,
  type CatalogImage,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
} from '../../services/api'
import { CatalogImageModal } from '../catalog/CatalogImageModal'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Pagination } from '../ui/Pagination'
import {
  IDENTITY_ACTION_HIDE_BREAKDOWN,
  IDENTITY_ACTION_SHOW_BREAKDOWN,
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  IDENTITY_BEST_PHOTOS_HELP,
  IDENTITY_COL_MODEL,
  IDENTITY_COL_PROMPT_VERSION,
  IDENTITY_COL_PERSPECTIVE,
  IDENTITY_COL_SCORE,
  IDENTITY_LABEL_AGGREGATE,
  IDENTITY_LABEL_PERSPECTIVES_COVERED,
  IDENTITY_SECTION_BEST_PHOTOS,
  MSG_LOADING,
  MSG_SHOWING_RANGE,
} from '../../constants/strings'

const PAGE_SIZE = 24

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function bestPhotoToCatalogStub(row: IdentityBestPhotoItem): CatalogImage {
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
    instagram_posted: Boolean(row.instagram_posted),
  }
}

function formatShowingRange(start: number, end: number, total: number): string {
  return MSG_SHOWING_RANGE.replace('{start}', String(start))
    .replace('{end}', String(end))
    .replace('{total}', String(total))
}

export function BestPhotosGrid() {
  const [page, setPage] = useState(1)
  const [rows, setRows] = useState<IdentityBestPhotoItem[]>([])
  const [total, setTotal] = useState(0)
  const [meta, setMeta] = useState<IdentityBestPhotosMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [selected, setSelected] = useState<CatalogImage | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const offset = (page - 1) * PAGE_SIZE
    try {
      const data = await IdentityAPI.getBestPhotos({
        limit: PAGE_SIZE,
        offset,
      })
      setRows(data.items)
      setTotal(data.total)
      setMeta(data.meta)
    } catch (e) {
      setError(errMessage(e))
      setRows([])
      setTotal(0)
      setMeta(null)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    void load()
  }, [load])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeLabel =
    total > 0
      ? formatShowingRange((page - 1) * PAGE_SIZE + 1, Math.min(page * PAGE_SIZE, total), total)
      : null

  const emptyMessage =
    !loading && !error && total === 0
      ? meta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK
      : null

  return (
    <section className="space-y-3" aria-labelledby="identity-best-photos-heading">
      <h2 id="identity-best-photos-heading" className="text-card-title text-text">
        {IDENTITY_SECTION_BEST_PHOTOS}
      </h2>
      <Card padding="md">
        <CardHeader>
          <CardTitle className="text-base sr-only">{IDENTITY_SECTION_BEST_PHOTOS}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 !text-text">
          <p className="text-sm text-text-secondary">{IDENTITY_BEST_PHOTOS_HELP}</p>

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
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {rows.map((row) => {
                  const open = expandedKey === row.image_key
                  const dateDisplay = row.date_taken
                    ? new Date(row.date_taken).toLocaleDateString()
                    : '—'
                  return (
                    <div
                      key={row.image_key}
                      className="rounded-card border border-border bg-bg shadow-card overflow-hidden"
                    >
                      <button
                        type="button"
                        onClick={() => setSelected(bestPhotoToCatalogStub(row))}
                        className="block w-full text-left focus:outline-none focus:ring-2 focus:ring-accent focus:ring-inset"
                      >
                        <div className="relative aspect-[4/3] bg-surface">
                          <img
                            src={`/api/images/catalog/${encodeURIComponent(row.image_key)}/thumbnail`}
                            alt={row.filename}
                            className="h-full w-full object-cover"
                            loading="lazy"
                          />
                        </div>
                      </button>
                      <div className="space-y-2 p-3">
                        <p className="truncate text-sm font-medium text-text">{row.filename}</p>
                        <p className="text-xs text-text-tertiary">{dateDisplay}</p>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-base bg-accent-light px-2 py-0.5 text-sm font-semibold text-accent">
                            {IDENTITY_LABEL_AGGREGATE}: {row.aggregate_score.toFixed(2)}
                          </span>
                          <span className="rounded-full border border-border px-2 py-0.5 text-xs text-text-secondary">
                            {IDENTITY_LABEL_PERSPECTIVES_COVERED}: {row.perspectives_covered}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedKey((k) => (k === row.image_key ? null : row.image_key))
                          }
                          className="text-sm font-medium text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent rounded-sm"
                          aria-expanded={open}
                        >
                          {open ? IDENTITY_ACTION_HIDE_BREAKDOWN : IDENTITY_ACTION_SHOW_BREAKDOWN}
                        </button>
                        {open ? (
                          <div className="overflow-x-auto rounded-base border border-border">
                            <table className="w-full min-w-[280px] text-left text-xs text-text">
                              <thead className="bg-surface text-text-secondary">
                                <tr>
                                  <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_PERSPECTIVE}</th>
                                  <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_SCORE}</th>
                                  <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_PROMPT_VERSION}</th>
                                  <th className="px-2 py-1.5 font-medium">{IDENTITY_COL_MODEL}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {row.per_perspective.map((p) => (
                                  <tr key={p.perspective_slug} className="border-t border-border">
                                    <td className="px-2 py-1.5">{p.display_name}</td>
                                    <td className="px-2 py-1.5 font-medium">{p.score}</td>
                                    <td className="px-2 py-1.5 text-text-secondary">
                                      {p.prompt_version || '—'}
                                    </td>
                                    <td className="px-2 py-1.5 text-text-secondary">
                                      {p.model_used || '—'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
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
        <CatalogImageModal image={selected} onClose={() => setSelected(null)} />
      ) : null}
    </section>
  )
}
