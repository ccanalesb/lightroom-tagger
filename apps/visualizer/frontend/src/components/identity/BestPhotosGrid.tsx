import { useEffect, useMemo, useState, useTransition, type MouseEventHandler } from 'react'
import {
  ImagesAPI,
  IdentityAPI,
  type CatalogImage,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
} from '../../services/api'
import { useQuery } from '../../data'
import { ImageDetailModal, ImageTile, fromBestPhotoRow, fromCatalogListRow } from '../image-view'
import { Button } from '../ui/Button/Button'
import { Badge, PerspectiveBadge } from '../ui/badges'
import { pickDominantPerspective } from './pickDominantPerspective'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import { Pagination } from '../ui/Pagination'
import { TileGrid } from '../ui/TileGrid'
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
  CATALOG_STACK_SHOW,
  CATALOG_STACK_HIDE,
  CATALOG_STACK_MEMBERS_ERROR,
  CATALOG_STACK_MEMBERS_LOADING,
  CATALOG_STACK_MEMBERS_REGION_ARIA,
  formatStackCountBadge,
} from '../../constants/strings'
import { FilterBar } from '../filters/FilterBar'
import { useFilters } from '../../hooks/useFilters'
import type { FilterSchema } from '../filters/types'

const PAGE_SIZE = 24

type BestPhotoSelection =
  | { kind: 'identity'; item: IdentityBestPhotoItem }
  | { kind: 'catalogMember'; initial: CatalogImage }

function BestPhotoTileWithStack({
  row,
  onOpenIdentity,
  onOpenCatalog,
}: {
  row: IdentityBestPhotoItem
  onOpenIdentity: (item: IdentityBestPhotoItem) => void
  onOpenCatalog: (c: CatalogImage) => void
}) {
  const stackId = row.stack_id
  const count = row.stack_member_count ?? 0
  const isRep = row.is_stack_representative === true
  const showStack = isRep && stackId != null && count > 1
  const regionId = `stack-members-bp-${row.image_key.replace(/[^a-zA-Z0-9_-]/g, '_')}`

  const [expanded, setExpanded] = useState(false)
  const [members, setMembers] = useState<CatalogImage[] | undefined>(undefined)
  const [loadError, setLoadError] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  const dom = pickDominantPerspective(row.per_perspective)

  const handleToggleStack: MouseEventHandler<HTMLButtonElement> = (e) => {
    e.stopPropagation()
    if (!showStack || stackId == null) return
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (members !== undefined) return
    setLoading(true)
    setLoadError(undefined)
    void ImagesAPI.getStackMembers(stackId)
      .then((res) => setMembers(res.items))
      .catch(() => setLoadError(CATALOG_STACK_MEMBERS_ERROR))
      .finally(() => setLoading(false))
  }

  return (
    <div className="min-w-0">
      <ImageTile
        image={fromBestPhotoRow(row)}
        variant="compact"
        primaryScoreSource="identity"
        onClick={() => onOpenIdentity(row)}
        overlayBadges={
          row.instagram_posted || showStack ? (
            <>
              {row.instagram_posted ? <Badge variant="success">Posted</Badge> : null}
              {showStack ? (
                <Badge variant="default">{formatStackCountBadge(count)}</Badge>
              ) : null}
            </>
          ) : undefined
        }
        hidePostedMetadataBadge
        footer={
          <div className="flex w-full flex-col gap-2">
            {dom ? (
              <PerspectiveBadge
                perspectiveSlug={dom.perspective_slug}
                score={dom.score}
                displayName={dom.display_name}
              />
            ) : null}
            {showStack ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                fullWidth
                className="min-h-11"
                aria-expanded={expanded}
                aria-controls={regionId}
                onClick={handleToggleStack}
              >
                {expanded ? CATALOG_STACK_HIDE : CATALOG_STACK_SHOW}
              </Button>
            ) : null}
          </div>
        }
      />
      {showStack && expanded ? (
        <div
          id={regionId}
          role="region"
          aria-label={CATALOG_STACK_MEMBERS_REGION_ARIA}
          className="mt-2 rounded-base border border-border bg-surface p-2"
        >
          {loading && members === undefined && !loadError ? (
            <p className="text-xs text-text-secondary">{CATALOG_STACK_MEMBERS_LOADING}</p>
          ) : null}
          {loadError ? (
            <p className="text-sm text-error" role="alert">
              {CATALOG_STACK_MEMBERS_ERROR}
            </p>
          ) : null}
          {members && !loadError ? (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {members.map((m) => (
                <div key={m.key} className="w-[7.5rem] shrink-0 min-w-0">
                  <ImageTile
                    image={fromCatalogListRow(m)}
                    variant="strip"
                    primaryScoreSource="catalog"
                    onClick={() => onOpenCatalog(m)}
                    className="!w-full max-w-full"
                  />
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function formatShowingRange(start: number, end: number, total: number): string {
  return MSG_SHOWING_RANGE.replace('{start}', String(start))
    .replace('{end}', String(end))
    .replace('{total}', String(total))
}

export function BestPhotosGrid() {
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<BestPhotoSelection | null>(null)
  const [isPending, startTransition] = useTransition()

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

  const sortKey = sortByDate ?? 'none'
  const data = useQuery(
    ['identity', 'best-photos', page, sortKey] as const,
    () =>
      IdentityAPI.getBestPhotos({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        sort_by_date:
          sortByDate && sortByDate !== 'none'
            ? (sortByDate as 'newest' | 'oldest')
            : undefined,
      }),
  )

  const rows = data.items
  const total = data.total
  const meta: IdentityBestPhotosMeta | undefined = data.meta

  useEffect(() => {
    startTransition(() => setPage(1))
  }, [sortByDate])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeLabel =
    total > 0
      ? formatShowingRange((page - 1) * PAGE_SIZE + 1, Math.min(page * PAGE_SIZE, total), total)
      : null

  const emptyMessage = total === 0 ? meta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK : null

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
            summary={rangeLabel ? <p className="text-sm text-text-secondary">{rangeLabel}</p> : null}
            disabled={false}
          />

          {emptyMessage ? (
            <p className="text-sm text-text-secondary" role="status">
              {emptyMessage}
            </p>
          ) : null}

          {rows.length > 0 ? (
            <div className={`transition-opacity duration-150${isPending ? ' opacity-50 pointer-events-none' : ''}`}>
              <TileGrid>
                {rows.map((row) => (
                  <BestPhotoTileWithStack
                    key={row.image_key}
                    row={row}
                    onOpenIdentity={(item) => setSelected({ kind: 'identity', item })}
                    onOpenCatalog={(c) => setSelected({ kind: 'catalogMember', initial: c })}
                  />
                ))}
              </TileGrid>
              {totalPages > 1 ? (
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={(p) => startTransition(() => setPage(p))}
                  disabled={isPending}
                />
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {selected?.kind === 'identity' ? (
        <ImageDetailModal
          imageType={(selected.item.image_type as 'catalog' | 'instagram') ?? 'catalog'}
          imageKey={selected.item.image_key}
          initialImage={fromBestPhotoRow(selected.item)}
          primaryScoreSource="identity"
          onClose={() => setSelected(null)}
        />
      ) : selected?.kind === 'catalogMember' ? (
        <ImageDetailModal
          imageType="catalog"
          imageKey={selected.initial.key}
          initialImage={fromCatalogListRow(selected.initial)}
          primaryScoreSource="catalog"
          onClose={() => setSelected(null)}
        />
      ) : null}
    </section>
  )
}
