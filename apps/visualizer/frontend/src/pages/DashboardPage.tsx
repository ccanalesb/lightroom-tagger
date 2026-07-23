import { Suspense, useMemo } from 'react'
import type { FilterSchema } from '../components/filters/types'
import { InsightsKpiRow } from '../components/insights/InsightsKpiRow'
import { InsightsQuickNav } from '../components/insights/InsightsQuickNav'
import { MiniPostingFrequencyChart } from '../components/insights/MiniPostingFrequencyChart'
import { TopPhotosStrip } from '../components/insights/TopPhotosStrip'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { TabNav } from '../components/ui/Tabs'
import {
  ANALYTICS_EMPTY_NO_POSTS,
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  INSIGHTS_FOOTER_TIMEZONE,
  INSIGHTS_PAGE_SUBTITLE,
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_POSTING_RANGE_NOTE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_SECTION_POSTING,
  INSIGHTS_TOP_PHOTOS_REGION_ARIA,
  INSIGHTS_TOP_PHOTOS_TAB_ALL,
  INSIGHTS_TOP_PHOTOS_TAB_POSTED,
  INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED,
} from '../constants/strings'
import { ErrorBoundary, ErrorState, useQuery } from '../data'
import { useFilters } from '../hooks/useFilters'
import {
  AnalyticsAPI,
  IdentityAPI,
  JobsAPI,
  SystemAPI,
  type IdentityBestPhotoItem,
  type IdentityBestPhotosMeta,
  type PostingFrequencyResponse,
  type Stats,
} from '../services/api'

function formatIsoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function defaultPostingRange(): { from: string; to: string } {
  const to = new Date()
  const from = new Date()
  from.setFullYear(from.getFullYear() - 1)
  return { from: formatIsoDate(from), to: formatIsoDate(to) }
}

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function sumBucketCounts(buckets: PostingFrequencyResponse['buckets']): number {
  return buckets.reduce((acc, b) => acc + b.count, 0)
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
  frequency: PostingFrequencyResponse | null
  errFrequency: string | null
  activeJobs: number
}

async function fetchDashboardBundle(postingRange: { from: string; to: string }): Promise<DashboardBundle> {
  const { from, to } = postingRange

  const results = await Promise.allSettled([
    SystemAPI.stats(),
    IdentityAPI.getBestPhotos({ limit: 8, posted: false }),
    IdentityAPI.getBestPhotos({ limit: 8, posted: true }),
    IdentityAPI.getBestPhotos({ limit: 8 }),
    AnalyticsAPI.getPostingFrequency({
      date_from: from,
      date_to: to,
      granularity: 'month',
    }),
    JobsAPI.list(),
  ])

  const [r0, r1, r2, r3, r4, r5] = results

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

  let frequency: PostingFrequencyResponse | null = null
  let errFrequency: string | null = null
  if (r4.status === 'fulfilled') {
    frequency = r4.value
  } else {
    errFrequency = errMessage(r4.reason)
  }

  let activeJobs = 0
  if (r5.status === 'fulfilled') {
    const jobsList = Array.isArray(r5.value?.data) ? r5.value.data : []
    activeJobs = jobsList.filter((job) => job.status === 'pending' || job.status === 'running').length
  }

  return {
    stats,
    errStats,
    topPhotosByTab,
    frequency,
    errFrequency,
    activeJobs,
  }
}

const dashboardSuspenseFallback = (
  <div className="rounded-card border border-border bg-surface p-8 text-center text-sm text-text-secondary">
    Loading…
  </div>
)

function DashboardPageInner() {
  const postingRange = useMemo(() => defaultPostingRange(), [])

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

  const bundle = useQuery(
    ['dashboard', postingRange.from, postingRange.to] as const,
    () => fetchDashboardBundle(postingRange),
  )

  const {
    stats,
    errStats,
    topPhotosByTab,
    frequency,
    errFrequency,
    activeJobs,
  } = bundle

  const loadingStats = false
  const loadingFrequency = false

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

  const postingBuckets = frequency?.buckets ?? []
  const postingTotal = sumBucketCounts(postingBuckets)
  const showPostingEmpty = !errFrequency && postingTotal === 0

  const a11yErrors = [
    errStats && `Stats: ${errStats}`,
    topPhotosByTab.unposted.error && `Best photos (unposted): ${topPhotosByTab.unposted.error}`,
    topPhotosByTab.posted.error && `Best photos (posted): ${topPhotosByTab.posted.error}`,
    topPhotosByTab.all.error && `Best photos (all): ${topPhotosByTab.all.error}`,
    errFrequency && `Posting frequency: ${errFrequency}`,
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

      <section className="space-y-3" aria-labelledby="insights-posting-heading">
        <h2 id="insights-posting-heading" className="text-card-title text-text">
          {INSIGHTS_SECTION_POSTING}
        </h2>
        <Card padding="md">
          <CardHeader>
            <CardTitle className="text-base sr-only">{INSIGHTS_SECTION_POSTING}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 !text-text">
            <p className="text-xs text-text-tertiary">{INSIGHTS_POSTING_RANGE_NOTE}</p>
            {showPostingEmpty ? (
              <div
                className="rounded-card border border-dashed border-border bg-surface px-4 py-3 text-sm text-text-secondary"
                role="status"
              >
                {ANALYTICS_EMPTY_NO_POSTS}
              </div>
            ) : (
              <MiniPostingFrequencyChart
                buckets={postingBuckets}
                meta={frequency?.meta ?? null}
                loading={loadingFrequency}
                error={errFrequency}
                rangeEndIso={postingRange.to}
              />
            )}
            {frequency?.meta?.timezone_assumption ? (
              <p className="text-xs text-text-secondary">
                <span className="font-medium text-text">Timezone assumption: </span>
                {frequency.meta.timezone_assumption}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

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
