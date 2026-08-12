import { Suspense, useMemo } from 'react'
import type { FilterSchema } from '../components/filters/types'
import { InsightsKpiRow } from '../components/insights/InsightsKpiRow'
import { InsightsQuickNav } from '../components/insights/InsightsQuickNav'
import { TopPhotosStrip } from '../components/insights/TopPhotosStrip'
import { Card, CardContent } from '../components/ui/Card'
import { TabNav } from '../components/ui/Tabs'
import {
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  INSIGHTS_FOOTER_TIMEZONE,
  INSIGHTS_PAGE_SUBTITLE,
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_TOP_PHOTOS_REGION_ARIA,
  INSIGHTS_TOP_PHOTOS_TAB_ALL,
  INSIGHTS_TOP_PHOTOS_TAB_POSTED,
  INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED,
} from '../constants/strings'
import { ErrorBoundary, ErrorState, useQuery } from '../data'
import { useFilters } from '../hooks/useFilters'
import {
  IdentityAPI,
  JobsAPI,
  SystemAPI,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
  type Stats,
} from '../services/api'

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

type TopPhotosTabKey = 'unposted' | 'posted' | 'all'

type TopPhotosBucket = {
  items: IdentityBestPhotoItem[]
  total: number
  meta: IdentityBestPhotosMeta | null
  loading: boolean
  error: string | null
}

type DashboardBundle = {
  stats: Stats | null
  errStats: string | null
  topPhotosByTab: Record<TopPhotosTabKey, TopPhotosBucket>
  activeJobs: number
}

async function fetchDashboardBundle(): Promise<DashboardBundle> {
  const results = await Promise.allSettled([
    SystemAPI.stats(),
    IdentityAPI.getBestPhotos({ limit: 8, posted: false }),
    IdentityAPI.getBestPhotos({ limit: 8, posted: true }),
    IdentityAPI.getBestPhotos({ limit: 8 }),
    JobsAPI.list(),
  ])

  const [r0, r1, r2, r3, r4] = results

  let stats: Stats | null = null
  let errStats: string | null = null
  if (r0.status === 'fulfilled') {
    stats = r0.value
  } else {
    errStats = errMessage(r0.reason)
  }

  const mapBest = (
    r: PromiseSettledResult<Awaited<ReturnType<typeof IdentityAPI.getBestPhotos>>>,
  ): TopPhotosBucket => {
    if (r.status === 'fulfilled') {
      return {
        items: r.value.items,
        total: r.value.total,
        meta: r.value.meta,
        loading: false,
        error: null,
      }
    }
    return {
      items: [],
      total: 0,
      meta: null,
      loading: false,
      error: errMessage(r.reason),
    }
  }

  const topPhotosByTab: Record<TopPhotosTabKey, TopPhotosBucket> = {
    unposted: mapBest(r1),
    posted: mapBest(r2),
    all: mapBest(r3),
  }

  let activeJobs = 0
  if (r4.status === 'fulfilled') {
    const jobsList = Array.isArray(r4.value?.data) ? r4.value.data : []
    activeJobs = jobsList.filter((job) => job.status === 'pending' || job.status === 'running').length
  }

  return {
    stats,
    errStats,
    topPhotosByTab,
    activeJobs,
  }
}

const dashboardSuspenseFallback = (
  <div className="rounded-card border border-border bg-surface p-8 text-center text-sm text-text-secondary">
    Loading…
  </div>
)

function DashboardPageInner() {
  const dashboardTopPhotosSchema = useMemo<FilterSchema>(
    () => [
      {
        type: 'select',
        key: 'topPhotosPosted',
        label: INSIGHTS_TOP_PHOTOS_REGION_ARIA,
        paramName: 'posted',
        defaultValue: 'unposted',
        options: [
          { value: 'unposted', label: INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED },
          { value: 'posted', label: INSIGHTS_TOP_PHOTOS_TAB_POSTED },
          { value: 'all', label: INSIGHTS_TOP_PHOTOS_TAB_ALL },
        ],
        toParam: (v) => (v === 'unposted' ? false : v === 'posted' ? true : undefined),
      },
    ],
    [],
  )

  const filters = useFilters(dashboardTopPhotosSchema)

  const bundle = useQuery(['dashboard'] as const, () => fetchDashboardBundle())

  const { stats, errStats, topPhotosByTab, activeJobs } = bundle

  const loadingStats = false

  const rawTopPhotosPosted = filters.values.topPhotosPosted as string | undefined
  const activeTopPhotosTab: TopPhotosTabKey =
    rawTopPhotosPosted === 'posted'
      ? 'posted'
      : rawTopPhotosPosted === 'all'
        ? 'all'
        : 'unposted'

  const activeTopPhotos = topPhotosByTab[activeTopPhotosTab]
  const bestEmptyMessage =
    !activeTopPhotos.loading &&
    !activeTopPhotos.error &&
    activeTopPhotos.total === 0
      ? activeTopPhotos.meta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK
      : null

  const a11yErrors = [
    errStats && `Stats: ${errStats}`,
    topPhotosByTab.unposted.error && `Best photos (unposted): ${topPhotosByTab.unposted.error}`,
    topPhotosByTab.posted.error && `Best photos (posted): ${topPhotosByTab.posted.error}`,
    topPhotosByTab.all.error && `Best photos (all): ${topPhotosByTab.all.error}`,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-section text-text mb-2">{INSIGHTS_PAGE_TITLE}</h1>
        <p className="text-text-secondary">{INSIGHTS_PAGE_SUBTITLE}</p>
      </div>

      <InsightsKpiRow
        stats={stats}
        activeJobs={activeJobs}
        loading={loadingStats}
        error={errStats}
      />

      {a11yErrors ? (
        <p className="sr-only" role="status" aria-live="polite">
          {a11yErrors}
        </p>
      ) : null}

      <section className="space-y-3" aria-labelledby="insights-highlights-heading">
        <h2 id="insights-highlights-heading" className="text-card-title text-text">
          {INSIGHTS_SECTION_HIGHLIGHTS}
        </h2>
        <Card padding="md">
          <CardContent className="!text-text">
            <div role="region" aria-label={INSIGHTS_TOP_PHOTOS_REGION_ARIA}>
              <TabNav
                tabs={[
                  { id: 'unposted', label: INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED },
                  { id: 'posted', label: INSIGHTS_TOP_PHOTOS_TAB_POSTED },
                  { id: 'all', label: INSIGHTS_TOP_PHOTOS_TAB_ALL },
                ]}
                activeTab={activeTopPhotosTab}
                onTabChange={(id) => filters.setValue('topPhotosPosted', id)}
              />
              <TopPhotosStrip
                items={activeTopPhotos.items}
                loading={activeTopPhotos.loading}
                error={activeTopPhotos.error}
                emptyMessage={bestEmptyMessage}
              />
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3" aria-labelledby="insights-explore-heading">
        <h2 id="insights-explore-heading" className="text-card-title text-text">
          {INSIGHTS_SECTION_EXPLORE}
        </h2>
        <InsightsQuickNav />
      </section>

      <footer className="border-t border-border pt-6 text-xs text-text-tertiary">
        <p>{INSIGHTS_FOOTER_TIMEZONE}</p>
      </footer>
    </div>
  )
}

export function DashboardPage() {
  return (
    <ErrorBoundary
      fallback={({ error, reset }) => (
        <ErrorState error={error} reset={reset} title="Could not load dashboard" />
      )}
    >
      <Suspense fallback={dashboardSuspenseFallback}>
        <DashboardPageInner />
      </Suspense>
    </ErrorBoundary>
  )
}
