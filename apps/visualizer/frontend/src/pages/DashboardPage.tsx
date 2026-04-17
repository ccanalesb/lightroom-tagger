import { useEffect, useMemo, useState } from 'react'
import { InsightsKpiRow } from '../components/insights/InsightsKpiRow'
import { InsightsQuickNav } from '../components/insights/InsightsQuickNav'
import { MiniPostingFrequencyChart } from '../components/insights/MiniPostingFrequencyChart'
import { PerspectiveRadarSummary } from '../components/insights/PerspectiveRadarSummary'
import { ScoreDistributionChart } from '../components/insights/ScoreDistributionChart'
import { TopPhotosStrip } from '../components/insights/TopPhotosStrip'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
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
} from '../constants/strings'
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

export function DashboardPage() {
  const postingRange = useMemo(() => defaultPostingRange(), [])

  const [stats, setStats] = useState<Stats | null>(null)
  const [errStats, setErrStats] = useState<string | null>(null)
  const [loadingStats, setLoadingStats] = useState(true)

  const [fingerprint, setFingerprint] = useState<StyleFingerprintResponse | null>(null)
  const [errFingerprint, setErrFingerprint] = useState<string | null>(null)
  const [loadingFingerprint, setLoadingFingerprint] = useState(true)

  const [bestItems, setBestItems] = useState<IdentityBestPhotoItem[]>([])
  const [bestMeta, setBestMeta] = useState<IdentityBestPhotosMeta | null>(null)
  const [bestTotal, setBestTotal] = useState(0)
  const [errBest, setErrBest] = useState<string | null>(null)
  const [loadingBest, setLoadingBest] = useState(true)

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
      setLoadingBest(true)
      setLoadingFrequency(true)
      setErrStats(null)
      setErrFingerprint(null)
      setErrBest(null)
      setErrFrequency(null)

      const results = await Promise.allSettled([
        SystemAPI.stats(),
        IdentityAPI.getStyleFingerprint(),
        IdentityAPI.getBestPhotos({ limit: 8 }),
        AnalyticsAPI.getPostingFrequency({
          date_from: from,
          date_to: to,
          granularity: 'month',
        }),
        JobsAPI.list(),
      ])

      if (cancelled) return

      const [r0, r1, r2, r3, r4] = results

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

      if (r2.status === 'fulfilled') {
        setBestItems(r2.value.items)
        setBestTotal(r2.value.total)
        setBestMeta(r2.value.meta)
        setErrBest(null)
      } else {
        setBestItems([])
        setBestTotal(0)
        setBestMeta(null)
        setErrBest(errMessage(r2.reason))
      }
      setLoadingBest(false)

      if (r3.status === 'fulfilled') {
        setFrequency(r3.value)
        setErrFrequency(null)
      } else {
        setFrequency(null)
        setErrFrequency(errMessage(r3.reason))
      }
      setLoadingFrequency(false)

      if (r4.status === 'fulfilled') {
        const jobsList = Array.isArray(r4.value?.data) ? r4.value.data : []
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

  const bestEmptyMessage =
    !loadingBest && !errBest && bestTotal === 0
      ? bestMeta?.coverage_note ?? IDENTITY_BEST_PHOTOS_EMPTY_FALLBACK
      : null

  const postingBuckets = frequency?.buckets ?? []
  const postingTotal = sumBucketCounts(postingBuckets)
  const showPostingEmpty = !loadingFrequency && !errFrequency && postingTotal === 0

  const a11yErrors = [
    errStats && `Stats: ${errStats}`,
    errFingerprint && `Style fingerprint: ${errFingerprint}`,
    errBest && `Best photos: ${errBest}`,
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
            <TopPhotosStrip
              items={bestItems}
              loading={loadingBest}
              error={errBest}
              emptyMessage={bestEmptyMessage}
            />
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
