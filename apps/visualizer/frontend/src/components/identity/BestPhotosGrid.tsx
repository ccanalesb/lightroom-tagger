import { useCallback, useEffect, useState } from 'react'
import {
  IdentityAPI,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
} from '../../services/api'
import {
  ImageDetailModal,
  ImagePerspectiveBreakdown,
  ImageTile,
  fromBestPhotoRow,
} from '../image-view'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Pagination } from '../ui/Pagination'
import {
  IDENTITY_ACTION_HIDE_BREAKDOWN,
  IDENTITY_ACTION_SHOW_BREAKDOWN,
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  IDENTITY_BEST_PHOTOS_HELP,
  IDENTITY_SECTION_BEST_PHOTOS,
  MSG_LOADING,
  MSG_SHOWING_RANGE,
} from '../../constants/strings'

const PAGE_SIZE = 24

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
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
  const [selected, setSelected] = useState<IdentityBestPhotoItem | null>(null)

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
                  return (
                    <ImageTile
                      key={row.image_key}
                      image={fromBestPhotoRow(row)}
                      variant="compact"
                      primaryScoreSource="identity"
                      onClick={() => setSelected(row)}
                      footer={
                        <div className="space-y-2 pt-1">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setExpandedKey((k) => (k === row.image_key ? null : row.image_key))
                            }}
                            className="text-sm font-medium text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent rounded-sm"
                            aria-expanded={open}
                          >
                            {open ? IDENTITY_ACTION_HIDE_BREAKDOWN : IDENTITY_ACTION_SHOW_BREAKDOWN}
                          </button>
                          {open ? (
                            <ImagePerspectiveBreakdown
                              perspectives={row.per_perspective}
                              aggregateScore={row.aggregate_score}
                              perspectivesCovered={row.perspectives_covered}
                              hideSummary
                            />
                          ) : null}
                        </div>
                      }
                    />
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
        <ImageDetailModal
          imageType={(selected.image_type as 'catalog' | 'instagram') ?? 'catalog'}
          imageKey={selected.image_key}
          initialImage={fromBestPhotoRow(selected)}
          primaryScoreSource="identity"
          onClose={() => setSelected(null)}
        />
      ) : null}
    </section>
  )
}
