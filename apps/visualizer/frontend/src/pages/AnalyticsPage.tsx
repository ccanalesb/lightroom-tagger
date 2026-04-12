import { useEffect, useMemo, useState } from 'react'
import { CaptionHashtagPanel } from '../components/analytics/CaptionHashtagPanel'
import { PostingFrequencyChart } from '../components/analytics/PostingFrequencyChart'
import { PostingHeatmap } from '../components/analytics/PostingHeatmap'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import {
  ANALYTICS_APPLY,
  ANALYTICS_GRANULARITY_DAY,
  ANALYTICS_GRANULARITY_MONTH,
  ANALYTICS_GRANULARITY_WEEK,
  ANALYTICS_LABEL_DATE_FROM,
  ANALYTICS_LABEL_DATE_TO,
  ANALYTICS_LABEL_GRANULARITY,
  ANALYTICS_PAGE_SUBTITLE,
  ANALYTICS_PAGE_TITLE,
  ANALYTICS_SECTION_CAPTIONS,
  ANALYTICS_SECTION_FREQUENCY,
  ANALYTICS_SECTION_HEATMAP,
  ANALYTICS_TIMEZONE_DISCLAIMER,
  ANALYTICS_EMPTY_NO_POSTS,
} from '../constants/strings'
import {
  AnalyticsAPI,
  type AnalyticsGranularity,
  type CaptionStatsResponse,
  type PostingFrequencyResponse,
  type PostingHeatmapResponse,
} from '../services/api'

function formatIsoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function defaultRange(): { from: string; to: string } {
  const to = new Date()
  const from = new Date()
  from.setFullYear(from.getFullYear() - 1)
  return { from: formatIsoDate(from), to: formatIsoDate(to) }
}

type AppliedFilters = { from: string; to: string; granularity: AnalyticsGranularity }

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

export function AnalyticsPage() {
  const initial = useMemo(() => {
    const r = defaultRange()
    return { ...r, granularity: 'day' as AnalyticsGranularity }
  }, [])

  const [dateFrom, setDateFrom] = useState(initial.from)
  const [dateTo, setDateTo] = useState(initial.to)
  const [granularity, setGranularity] = useState<AnalyticsGranularity>(initial.granularity)
  const [applied, setApplied] = useState<AppliedFilters>(initial)

  const [loading, setLoading] = useState(true)
  const [frequency, setFrequency] = useState<PostingFrequencyResponse | null>(null)
  const [heatmap, setHeatmap] = useState<PostingHeatmapResponse | null>(null)
  const [captions, setCaptions] = useState<CaptionStatsResponse | null>(null)
  const [errFreq, setErrFreq] = useState<string | null>(null)
  const [errHeat, setErrHeat] = useState<string | null>(null)
  const [errCap, setErrCap] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const filters = applied

    async function run() {
      setLoading(true)
      setErrFreq(null)
      setErrHeat(null)
      setErrCap(null)

      if (filters.from > filters.to) {
        const msg = 'Start date must be on or before end date.'
        if (cancelled) return
        setErrFreq(msg)
        setErrHeat(msg)
        setErrCap(msg)
        setFrequency(null)
        setHeatmap(null)
        setCaptions(null)
        setLoading(false)
        return
      }

      const results = await Promise.allSettled([
        AnalyticsAPI.getPostingFrequency({
          date_from: filters.from,
          date_to: filters.to,
          granularity: filters.granularity,
        }),
        AnalyticsAPI.getPostingHeatmap({
          date_from: filters.from,
          date_to: filters.to,
        }),
        AnalyticsAPI.getCaptionStats({
          date_from: filters.from,
          date_to: filters.to,
        }),
      ])

      if (cancelled) return

      const [r0, r1, r2] = results

      if (r0.status === 'fulfilled') {
        setFrequency(r0.value)
        setErrFreq(null)
      } else {
        setFrequency(null)
        setErrFreq(errMessage(r0.reason))
      }

      if (r1.status === 'fulfilled') {
        setHeatmap(r1.value)
        setErrHeat(null)
      } else {
        setHeatmap(null)
        setErrHeat(errMessage(r1.reason))
      }

      if (r2.status === 'fulfilled') {
        setCaptions(r2.value)
        setErrCap(null)
      } else {
        setCaptions(null)
        setErrCap(errMessage(r2.reason))
      }

      setLoading(false)
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [applied])

  const handleApply = () => {
    setApplied({ from: dateFrom, to: dateTo, granularity })
  }

  const a11yErrors = [
    errFreq && `Posting frequency: ${errFreq}`,
    errHeat && `Heatmap: ${errHeat}`,
    errCap && `Captions: ${errCap}`,
  ]
    .filter(Boolean)
    .join(' ')

  const showEmptyHint =
    !loading &&
    captions &&
    captions.post_count === 0 &&
    !errFreq &&
    !errHeat &&
    !errCap

  const footerPieces = useMemo(() => {
    const tz =
      frequency?.meta?.timezone_assumption ??
      heatmap?.meta?.timezone_assumption ??
      captions?.meta?.timezone_assumption
    const note = heatmap?.meta?.timezone_note
    const capScope = captions?.meta?.timestamp_scope
    return { tz, note, capScope }
  }, [frequency, heatmap, captions])

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-section text-text mb-2">{ANALYTICS_PAGE_TITLE}</h1>
        <p className="text-text-secondary">{ANALYTICS_PAGE_SUBTITLE}</p>
      </div>

      <Card padding="md">
        <CardHeader>
          <CardTitle className="text-base">Date range</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="analytics-date-from" className="text-sm font-medium text-text">
                {ANALYTICS_LABEL_DATE_FROM}
              </label>
              <input
                id="analytics-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="analytics-date-to" className="text-sm font-medium text-text">
                {ANALYTICS_LABEL_DATE_TO}
              </label>
              <input
                id="analytics-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div className="flex min-w-[10rem] flex-col gap-1">
              <label htmlFor="analytics-granularity" className="text-sm font-medium text-text">
                {ANALYTICS_LABEL_GRANULARITY}
              </label>
              <select
                id="analytics-granularity"
                value={granularity}
                onChange={(e) => setGranularity(e.target.value as AnalyticsGranularity)}
                className="rounded-base border border-border bg-bg px-3 py-2 text-sm text-text shadow-sm focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <option value="day">{ANALYTICS_GRANULARITY_DAY}</option>
                <option value="week">{ANALYTICS_GRANULARITY_WEEK}</option>
                <option value="month">{ANALYTICS_GRANULARITY_MONTH}</option>
              </select>
            </div>
            <button
              type="button"
              onClick={handleApply}
              className="rounded-base bg-accent px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg"
            >
              {ANALYTICS_APPLY}
            </button>
          </div>
        </CardContent>
      </Card>

      {a11yErrors ? (
        <p className="sr-only" role="status" aria-live="polite">
          {a11yErrors}
        </p>
      ) : null}

      {showEmptyHint ? (
        <div
          className="rounded-card border border-dashed border-border bg-surface px-4 py-3 text-sm text-text-secondary"
          role="status"
        >
          {ANALYTICS_EMPTY_NO_POSTS}
        </div>
      ) : null}

      <section className="space-y-3" aria-labelledby="analytics-frequency-heading">
        <h2 id="analytics-frequency-heading" className="text-card-title text-text">
          {ANALYTICS_SECTION_FREQUENCY}
        </h2>
        <Card padding="md">
          <CardContent className="!text-text">
            <PostingFrequencyChart
              buckets={frequency?.buckets ?? []}
              meta={frequency?.meta ?? null}
              loading={loading}
              error={errFreq}
            />
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3" aria-labelledby="analytics-heatmap-heading">
        <h2 id="analytics-heatmap-heading" className="text-card-title text-text">
          {ANALYTICS_SECTION_HEATMAP}
        </h2>
        <Card padding="md">
          <CardContent className="!text-text">
            <PostingHeatmap
              cells={heatmap?.cells ?? []}
              meta={heatmap?.meta ?? null}
              loading={loading}
              error={errHeat}
            />
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3" aria-labelledby="analytics-caption-heading">
        <h2 id="analytics-caption-heading" className="text-card-title text-text">
          {ANALYTICS_SECTION_CAPTIONS}
        </h2>
        <CaptionHashtagPanel stats={captions} loading={loading} error={errCap} />
      </section>

      <footer className="border-t border-border pt-6 text-xs text-text-tertiary space-y-2">
        <p>{ANALYTICS_TIMEZONE_DISCLAIMER}</p>
        {footerPieces.tz ? (
          <p>
            <span className="font-medium text-text-secondary">Timezone assumption: </span>
            {footerPieces.tz}
          </p>
        ) : null}
        {footerPieces.note ? (
          <p>
            <span className="font-medium text-text-secondary">Heatmap: </span>
            {footerPieces.note}
          </p>
        ) : null}
        {footerPieces.capScope ? (
          <p>
            <span className="font-medium text-text-secondary">Caption scope: </span>
            {footerPieces.capScope}
          </p>
        ) : null}
      </footer>
    </div>
  )
}
