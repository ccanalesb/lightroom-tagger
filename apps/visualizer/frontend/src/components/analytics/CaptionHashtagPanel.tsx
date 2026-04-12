import type { CaptionStatsResponse } from '../../services/api'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  ANALYTICS_CAPTION_STATS,
  ANALYTICS_CAPTION_TOP_HASHTAGS,
  ANALYTICS_COL_COUNT,
  ANALYTICS_COL_HASHTAG,
  ANALYTICS_EMPTY_NO_POSTS,
  ANALYTICS_STAT_AVG_LEN,
  ANALYTICS_STAT_AVG_TAGS,
  ANALYTICS_STAT_MEDIAN_LEN,
  ANALYTICS_STAT_POSTS,
  ANALYTICS_STAT_POSTS_WITH_TAGS,
  ANALYTICS_STAT_WITH_CAPTION,
  MSG_LOADING,
} from '../../constants/strings'

export interface CaptionHashtagPanelProps {
  stats: CaptionStatsResponse | null
  loading: boolean
  error: string | null
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border py-2 last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className="font-medium tabular-nums text-text">{value}</span>
    </div>
  )
}

export function CaptionHashtagPanel({ stats, loading, error }: CaptionHashtagPanelProps) {
  if (loading) {
    return (
      <Card padding="md">
        <CardHeader>
          <CardTitle>{ANALYTICS_CAPTION_STATS}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-secondary" role="status" aria-live="polite">
            {MSG_LOADING}
          </p>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card padding="md">
        <CardHeader>
          <CardTitle>{ANALYTICS_CAPTION_STATS}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-error" role="alert">
            {error}
          </p>
        </CardContent>
      </Card>
    )
  }

  if (!stats || stats.post_count === 0) {
    return (
      <Card padding="md">
        <CardHeader>
          <CardTitle>{ANALYTICS_CAPTION_STATS}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-secondary">{ANALYTICS_EMPTY_NO_POSTS}</p>
        </CardContent>
      </Card>
    )
  }

  const top = stats.top_hashtags ?? []
  const maxTag = top.reduce((m, t) => Math.max(m, t.count), 0) || 1

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card padding="md">
        <CardHeader>
          <CardTitle>{ANALYTICS_CAPTION_STATS}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-0">
          <StatRow label={ANALYTICS_STAT_POSTS} value={stats.post_count.toLocaleString()} />
          <StatRow
            label={ANALYTICS_STAT_WITH_CAPTION}
            value={stats.with_caption_count.toLocaleString()}
          />
          <StatRow
            label={ANALYTICS_STAT_AVG_LEN}
            value={stats.avg_caption_len.toFixed(1)}
          />
          <StatRow
            label={ANALYTICS_STAT_MEDIAN_LEN}
            value={
              stats.median_caption_len != null ? stats.median_caption_len.toFixed(1) : '—'
            }
          />
          <StatRow
            label={ANALYTICS_STAT_POSTS_WITH_TAGS}
            value={stats.posts_with_hashtags.toLocaleString()}
          />
          <StatRow
            label={ANALYTICS_STAT_AVG_TAGS}
            value={stats.avg_hashtags_per_post.toFixed(2)}
          />
        </CardContent>
      </Card>

      <Card padding="md">
        <CardHeader>
          <CardTitle>{ANALYTICS_CAPTION_TOP_HASHTAGS}</CardTitle>
        </CardHeader>
        <CardContent>
          {top.length === 0 ? (
            <p className="text-sm text-text-secondary">No hashtags in this range.</p>
          ) : (
            <div
              className="max-h-[320px] overflow-y-auto rounded-base border border-border"
              role="region"
              aria-label={ANALYTICS_CAPTION_TOP_HASHTAGS}
            >
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-surface text-xs uppercase tracking-wide text-text-tertiary">
                  <tr>
                    <th className="px-3 py-2 font-medium">{ANALYTICS_COL_HASHTAG}</th>
                    <th className="px-3 py-2 font-medium text-right">{ANALYTICS_COL_COUNT}</th>
                    <th className="w-[40%] px-3 py-2 font-medium" aria-hidden>
                      {/* bar */}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {top.map((row) => (
                    <tr key={row.tag} className="border-t border-border">
                      <td className="px-3 py-2 font-medium text-text">#{row.tag}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-text-secondary">
                        {row.count.toLocaleString()}
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <div
                          className="h-2 rounded-full bg-surface"
                          title={`${row.count} posts`}
                        >
                          <div
                            className="h-2 rounded-full bg-accent"
                            style={{
                              width: `${Math.max(8, (row.count / maxTag) * 100)}%`,
                              maxWidth: '100%',
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
