import { useEffect, useMemo, useState } from 'react'
import type { FilterSchema } from '../components/filters/types'
import { InsightsKpiRow } from '../components/insights/InsightsKpiRow'
import { InsightsQuickNav } from '../components/insights/InsightsQuickNav'
import { MiniPostingFrequencyChart } from '../components/insights/MiniPostingFrequencyChart'
import { PerspectiveRadarSummary } from '../components/insights/PerspectiveRadarSummary'
import { ScoreDistributionChart } from '../components/insights/ScoreDistributionChart'
import { TopPhotosStrip } from '../components/insights/TopPhotosStrip'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { TabNav } from '../components/ui/Tabs'
import {
  ANALYTICS_EMPTY_NO_POSTS,
  IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK,
  INSIGHTS_EMPTY_FINGERPRINT,
  INSIGHTS_FOOTER_TIMEZONE,
  INSIGHTS_PAGE_SUBTITLE,
  INSIGHTS_PAGE_TITLE,
  INSIGHTS_POSTING_RANGE_NOTE,
  INSIGHTS_SECTION_EXPLORE,
  INSIGHTS_SECTION_HIGHLIGHTS,
  INSIGHTS_SECTION_POSTING,
  INSIGHTS_SECTION_SCORES,
  INSIGHTS_TOP_PHOTOS_REGION_ARIA,
  INSIGHTS_TOP_PHOTOS_TAB_ALL,
  INSIGHTS_TOP_PHOTOS_TAB_POSTED,
  INSIGHTS_TOP_PHOTOS_TAB_UNPOSTED,
} from '../constants/strings'
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
  type StyleFingerprintResponse,
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

function totalScoreCount(per: StyleFingerprintResponse['per_perspective']): number {
  return per.reduce((acc, p) => acc + (p.count_scores || 0), 0)
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

function emptyTopPhotosBucket(loading: boolean): TopPhotosBucket {
  return { items: [], total: 0, meta: null, loading, error: null }
}

export function DashboardPage() {
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

  const [stats, setStats] = useState<Stats | null>(null)
  const [errStats, setErrStats] = useState<string | null>(null)
  const [loadingStats, setLoadingStats] = useState(true)

  const [fingerprint, setFingerprint] = useState<StyleFingerprintResponse | null>(null)
  const [errFingerprint, setErrFingerprint] = useState<string | null>(null)
  const [loadingFingerprint, setLoadingFingerprint] = useState(true)

  const [topPhotosByTab, setTopPhotosByTab] = useState<Record<TopPhotosTabKey, TopPhotosBucket>>(() => ({
    unposted: emptyTopPhotosBucket(true),
    posted: emptyTopPhotosBucket(true),
    all: emptyTopPhotosBucket(true),
  }))

  const [frequency, setFrequency] = useState<PostingFrequencyResponse | null>(null)
  const [errFrequency, setErrFrequency] = useState<string | null>(null)
  const [loadingFrequency, setLoadingFrequency] = useState(true)

  const [activeJobs, setActiveJobs] = useState(0)

  useEffect(() => {
    let cancelled = false
    const { from, to } = postingRange

    async function run() {
      setLoadingStats(true)
      setLoadingFingerprint(true)
      setLoadingFrequency(true)
      setErrStats(null)
      setErrFingerprint(null)
      setErrFrequency(null)
      setTopPhotosByTab({
        unposted: emptyTopPhotosBucket(true),
        posted: emptyTopPhotosBucket(true),
        all: emptyTopPhotosBucket(true),
      })

      const results = await Promise.allSettled([
        SystemAPI.stats(),
        IdentityAPI.getStyleFingerprint(),
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

      if (cancelled) return

      const [r0, r1, r2, r3, r4, r5, r6] = results

      if (r0.status === 'fulfilled') {
        setStats(r0.value)
        setErrStats(null)
      } else {
        setStats(null)
        setErrStats(errMessage(r0.reason))
      }
      setLoadingStats(false)

      if (r1.status === 'fulfilled') {
        setFingerprint(r1.value)
        setErrFingerprint(null)
      } else {
        setFingerprint(null)
        setErrFingerprint(errMessage(r1.reason))
      }
      setLoadingFingerprint(false)

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

      setTopPhotosByTab({
        unposted: mapBest(r2),
        posted: mapBest(r3),
        all: mapBest(r4),
      })

      if (r5.status === 'fulfilled') {
        setFrequency(r5.value)
        setErrFrequency(null)
      } else {
        setFrequency(null)
        setErrFrequency(errMessage(r5.reason))
      }
      setLoadingFrequency(false)

      if (r6.status === 'fulfilled') {
        const jobsList = Array.isArray(r6.value?.data) ? r6.value.data : []
        const pending = jobsList.filter(
          (job) => job.status === 'pending' || job.status === 'running',
        ).length
        setActiveJobs(pending)
      } else {
        setActiveJobs(0)
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [postingRange])

  const fpNoScores =
    fingerprint && !errFingerprint && totalScoreCount(fingerprint.per_perspective) === 0

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
  const showPostingEmpty = !loadingFrequency && !errFrequency && postingTotal === 0

  const a11yErrors = [
    errStats && `Stats: ${errStats}`,
    errFingerprint && `Style fingerprint: ${errFingerprint}`,
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

      <section className="space-y-3" aria-labelledby="insights-scores-heading">
        <h2 id="insights-scores-heading" className="text-card-title text-text">
          {INSIGHTS_SECTION_SCORES}
        </h2>
        {fpNoScores ? (
          <div
            className="rounded-card border border-dashed border-border bg-surface px-4 py-3 text-sm text-text-secondary"
            role="status"
          >
            {INSIGHTS_EMPTY_FINGERPRINT}
          </div>
        ) : null}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card padding="md">
            <CardHeader>
              <CardTitle className="text-base sr-only">{INSIGHTS_SECTION_SCORES}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6 !text-text">
              <ScoreDistributionChart
                aggregateDistribution={fingerprint?.aggregate_distribution ?? null}
                note={fingerprint?.aggregate_distribution_note}
                loading={loadingFingerprint}
                error={errFingerprint}
              />
              <PerspectiveRadarSummary
                perPerspective={fingerprint?.per_perspective ?? null}
                loading={loadingFingerprint}
                error={errFingerprint}
              />
              {fingerprint?.meta?.scores_are_advisory ? (
                <p className="text-xs text-text-tertiary">{fingerprint.meta.scores_are_advisory}</p>
              ) : null}
            </CardContent>
          </Card>

          <Card padding="md">
            <CardHeader>
              <CardTitle className="text-base">{INSIGHTS_SECTION_POSTING}</CardTitle>
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
        </div>
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
