import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { IdentityAPI, type StyleFingerprintResponse } from '../../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  IDENTITY_FINGERPRINT_CHART_TITLE,
  IDENTITY_FINGERPRINT_DISTRIBUTION,
  IDENTITY_FINGERPRINT_EMPTY,
  IDENTITY_FINGERPRINT_EVIDENCE,
  IDENTITY_FINGERPRINT_LOW_DATA,
  IDENTITY_FINGERPRINT_TOKENS,
  IDENTITY_INTRO_STYLE_FINGERPRINT,
  IDENTITY_SECTION_STYLE_FINGERPRINT,
  MSG_LOADING,
} from '../../constants/strings'

const CHART_STROKE = 'var(--color-accent)'
const CHART_FILL = 'var(--color-accent-light)'
const AXIS_STROKE = 'var(--color-text-tertiary)'
const GRID_STROKE = 'var(--color-border)'

function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message
  return String(e)
}

function totalScoreCount(per: StyleFingerprintResponse['per_perspective']): number {
  return per.reduce((acc, p) => acc + (p.count_scores || 0), 0)
}

export function StyleFingerprintPanel() {
  const [data, setData] = useState<StyleFingerprintResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    IdentityAPI.getStyleFingerprint()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(errMessage(e))
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const radarRows = useMemo(() => {
    if (!data) return []
    return data.per_perspective
      .filter((p) => p.mean_score != null && p.count_scores > 0)
      .map((p) => ({
        axis: p.perspective_slug.replace(/_/g, ' '),
        mean: Number(p.mean_score),
        fullSlug: p.perspective_slug,
      }))
  }, [data])

  const histRows = useMemo(() => {
    if (!data) return []
    return Object.entries(data.aggregate_distribution).map(([label, count]) => ({
      label,
      count,
    }))
  }, [data])

  const noScores = data && totalScoreCount(data.per_perspective) === 0
  const showLowDataHint =
    data && !noScores && data.per_perspective.some((p) => p.count_scores === 0)

  if (loading) {
    return (
      <section className="space-y-3" aria-labelledby="identity-fingerprint-heading">
        <h2 id="identity-fingerprint-heading" className="text-card-title text-text">
          {IDENTITY_SECTION_STYLE_FINGERPRINT}
        </h2>
        <p className="text-sm text-text-secondary">{IDENTITY_INTRO_STYLE_FINGERPRINT}</p>
        <Card padding="md">
          <CardContent>
            <p className="text-sm text-text-secondary" role="status" aria-live="polite">
              {MSG_LOADING}
            </p>
          </CardContent>
        </Card>
      </section>
    )
  }

  if (error) {
    return (
      <section className="space-y-3" aria-labelledby="identity-fingerprint-heading">
        <h2 id="identity-fingerprint-heading" className="text-card-title text-text">
          {IDENTITY_SECTION_STYLE_FINGERPRINT}
        </h2>
        <p className="text-sm text-text-secondary">{IDENTITY_INTRO_STYLE_FINGERPRINT}</p>
        <Card padding="md">
          <CardContent>
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          </CardContent>
        </Card>
      </section>
    )
  }

  if (!data || noScores || radarRows.length === 0) {
    return (
      <section className="space-y-3" aria-labelledby="identity-fingerprint-heading">
        <h2 id="identity-fingerprint-heading" className="text-card-title text-text">
          {IDENTITY_SECTION_STYLE_FINGERPRINT}
        </h2>
        <p className="text-sm text-text-secondary">{IDENTITY_INTRO_STYLE_FINGERPRINT}</p>
        <Card padding="md">
          <CardContent>
            <p className="text-sm text-text-secondary" role="status">
              {IDENTITY_FINGERPRINT_EMPTY}
            </p>
          </CardContent>
        </Card>
      </section>
    )
  }

  return (
    <section className="space-y-3" aria-labelledby="identity-fingerprint-heading">
      <h2 id="identity-fingerprint-heading" className="text-card-title text-text">
        {IDENTITY_SECTION_STYLE_FINGERPRINT}
      </h2>
      <p className="text-sm text-text-secondary">{IDENTITY_INTRO_STYLE_FINGERPRINT}</p>
      <Card padding="md">
        <CardHeader>
          <CardTitle className="text-base">{IDENTITY_FINGERPRINT_CHART_TITLE}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8 !text-text">
          {showLowDataHint ? (
            <p className="text-sm text-text-secondary" role="status">
              {IDENTITY_FINGERPRINT_LOW_DATA}
            </p>
          ) : null}

          <div className="h-[320px] w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarRows} margin={{ top: 16, right: 24, bottom: 16, left: 24 }}>
                <PolarGrid stroke={GRID_STROKE} />
                <PolarAngleAxis dataKey="axis" tick={{ fill: AXIS_STROKE, fontSize: 11 }} />
                <Radar
                  name="Mean"
                  dataKey="mean"
                  stroke={CHART_STROKE}
                  fill={CHART_FILL}
                  fillOpacity={0.45}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    color: 'var(--color-text)',
                  }}
                  formatter={(value) => {
                    const n = typeof value === 'number' ? value : Number(value)
                    return [Number.isFinite(n) ? n.toFixed(2) : '—', 'Mean score']
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-text">{IDENTITY_FINGERPRINT_DISTRIBUTION}</h3>
            {data.aggregate_distribution_note ? (
              <p className="text-xs text-text-tertiary">{data.aggregate_distribution_note}</p>
            ) : null}
            <div className="h-[220px] w-full min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={histRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: AXIS_STROKE, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: GRID_STROKE }}
                  />
                  <YAxis
                    tick={{ fill: AXIS_STROKE, fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                    width={36}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: '8px',
                      color: 'var(--color-text)',
                    }}
                    formatter={(value) => [value ?? '—', 'Images']}
                  />
                  <Bar dataKey="count" fill={CHART_STROKE} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-text">{IDENTITY_FINGERPRINT_TOKENS}</h3>
            <p className="text-xs text-text-tertiary">{data.meta?.tokenization_note}</p>
            <ul className="flex max-h-40 flex-wrap gap-2 overflow-y-auto rounded-base border border-border bg-surface p-3 text-xs text-text">
              {data.top_rationale_tokens.length === 0 ? (
                <li className="text-text-secondary">—</li>
              ) : (
                data.top_rationale_tokens.map((t) => (
                  <li
                    key={t.token}
                    className="rounded-full border border-border bg-bg px-2 py-0.5 text-text-secondary"
                  >
                    <span className="font-medium text-text">{t.token}</span>
                    <span className="text-text-tertiary"> · {t.count}</span>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-text">{IDENTITY_FINGERPRINT_EVIDENCE}</h3>
            {data.evidence_note ? (
              <p className="text-xs text-text-tertiary">{data.evidence_note}</p>
            ) : null}
            <ul className="space-y-3 text-sm">
              {Object.entries(data.evidence).map(([slug, keys]) => (
                <li key={slug}>
                  <span className="font-medium text-text-secondary">{slug}</span>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {keys.map((k) => (
                      <Link
                        key={k}
                        to={`/images?tab=catalog&image_key=${encodeURIComponent(k)}`}
                        className="rounded-base border border-border bg-bg px-2 py-1 text-xs text-accent hover:bg-surface focus:outline-none focus:ring-2 focus:ring-accent"
                      >
                        {k.length > 24 ? `${k.slice(0, 24)}…` : k}
                      </Link>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {data.meta?.scores_are_advisory ? (
            <p className="text-xs text-text-tertiary">{data.meta.scores_are_advisory}</p>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}
