import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  IdentityAPI,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
} from '../../services/api'
import { ImageDetailModal, ImageTile, fromBestPhotoRow } from '../image-view'
import { Badge } from '../ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Pagination } from '../ui/Pagination'
import { TileGrid } from '../ui/TileGrid'
import { SkeletonGrid } from '../ui/page-states'
import {
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  IDENTITY_BEST_PHOTOS_HELP,
  IDENTITY_INTRO_BEST_PHOTOS,
  IDENTITY_SECTION_BEST_PHOTOS,
  MSG_SHOWING_RANGE,
  FILTER_LABEL_SORT_DATE,
  FILTER_SORT_DATE_NEWEST,
  FILTER_SORT_DATE_OLDEST,
  FILTER_SORT_DATE_NONE,
} from '../../constants/strings'
import { FilterBar } from '../filters/FilterBar'
import { useFilters } from '../../hooks/useFilters'
import type { FilterSchema } from '../filters/types'

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
  const [selected, setSelected] = useState<IdentityBestPhotoItem | null>(null)

  const bestPhotosSchema = useMemo<FilterSchema>(
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
  const filters = useFilters(bestPhotosSchema)
  const sortByDate = filters.values.sortByDate as string | undefined

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const offset = (page - 1) * PAGE_SIZE
    try {
      const data = await IdentityAPI.getBestPhotos({
        limit: PAGE_SIZE,
        offset,
        sort_by_date:
          sortByDate && sortByDate !== 'none'
            ? (sortByDate as 'newest' | 'oldest')
            : undefined,
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
  }, [page, sortByDate])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [sortByDate])

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
      <p className="text-sm text-text-secondary">{IDENTITY_INTRO_BEST_PHOTOS}</p>
      <Card padding="md">
        <CardHeader>
          <CardTitle className="text-base sr-only">{IDENTITY_SECTION_BEST_PHOTOS}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 !text-text">
          <p className="text-sm text-text-secondary">{IDENTITY_BEST_PHOTOS_HELP}</p>
          <FilterBar
            schema={bestPhotosSchema}
            filters={filters}
            summary={
              !loading && !error && rangeLabel ? (
                <p className="text-sm text-text-secondary">{rangeLabel}</p>
              ) : null
            }
            disabled={loading}
          />

          {loading ? <SkeletonGrid count={PAGE_SIZE} /> : null}

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
              <TileGrid>
                {rows.map((row) => (
                  <ImageTile
                    key={row.image_key}
                    image={fromBestPhotoRow(row)}
                    variant="compact"
                    primaryScoreSource="identity"
                    onClick={() => setSelected(row)}
                    overlayBadges={
                      row.instagram_posted ? (
                        <Badge variant="success">Posted</Badge>
                      ) : undefined
                    }
                    hidePostedMetadataBadge={true}
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
