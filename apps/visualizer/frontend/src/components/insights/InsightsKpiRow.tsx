import { Link } from 'react-router-dom'
import type { Stats } from '../../services/api'
import { Badge } from '../ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  DASHBOARD_CATALOG_IMAGES,
  DASHBOARD_INSTAGRAM_IMAGES,
  DASHBOARD_MATCHES,
  DASHBOARD_POSTED,
  INSIGHTS_KPI_ACTIVE_JOBS,
  INSIGHTS_KPI_ACTIVE_JOBS_DESC,
  MSG_LOADING,
} from '../../constants/strings'

export type InsightsKpiRowProps = {
  stats: Stats | null
  activeJobs: number
  loading: boolean
  error: string | null
}

type StatBadge = 'default' | 'success' | 'accent'

export function InsightsKpiRow({ stats, activeJobs, loading, error }: InsightsKpiRowProps) {
  if (error) {
    return (
      <div className="rounded-card border border-border bg-surface px-4 py-3 text-sm text-error" role="alert">
        {error}
      </div>
    )
  }

  if (loading) {
    return (
      <p className="text-sm text-text-secondary" role="status" aria-live="polite">
        {MSG_LOADING}
      </p>
    )
  }

  const catalog = stats?.catalog_images ?? 0
  const instagram = stats?.instagram_images ?? 0
  const posted = stats?.posted_to_instagram ?? 0
  const matches = stats?.matches_found ?? 0

  const cards: Array<{
    title: string
    value: string
    description: string
    link: string
    badge: StatBadge
  }> = [
    {
      title: DASHBOARD_CATALOG_IMAGES,
      value: catalog.toLocaleString(),
      description: 'Lightroom catalog entries',
      link: '/images?tab=catalog',
      badge: catalog > 0 ? 'success' : 'default',
    },
    {
      title: DASHBOARD_INSTAGRAM_IMAGES,
      value: instagram.toLocaleString(),
      description: 'From Instagram dump',
      link: '/images?tab=instagram',
      badge: instagram > 0 ? 'success' : 'default',
    },
    {
      title: DASHBOARD_POSTED,
      value: posted.toLocaleString(),
      description: 'Marked posted to Instagram',
      link: '/analytics',
      badge: posted > 0 ? 'success' : 'default',
    },
    {
      title: DASHBOARD_MATCHES,
      value: matches.toLocaleString(),
      description: 'Catalog ↔ Instagram pairs',
      link: '/images?tab=matches',
      badge: matches > 0 ? 'success' : 'default',
    },
    {
      title: INSIGHTS_KPI_ACTIVE_JOBS,
      value: activeJobs.toLocaleString(),
      description: INSIGHTS_KPI_ACTIVE_JOBS_DESC,
      link: '/processing?tab=jobs',
      badge: activeJobs > 0 ? 'accent' : 'default',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((stat) => (
        <Link key={stat.title} to={stat.link}>
          <Card hoverable padding="md">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-sm leading-snug">{stat.title}</CardTitle>
                <Badge variant={stat.badge}>{stat.value}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-text-secondary">{stat.description}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}
