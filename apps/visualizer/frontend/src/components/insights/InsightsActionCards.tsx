import { Link } from 'react-router-dom'
import type { InsightsSummary } from '../../services/api'
import { Badge } from '../ui/badges'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  INSIGHTS_ACTION_CULL_BURST,
  INSIGHTS_ACTION_CULL_BURST_DESC,
  INSIGHTS_ACTION_FINISH_PASS,
  INSIGHTS_ACTION_FINISH_PASS_DESC,
  INSIGHTS_LINK_BURST_STACKS,
  INSIGHTS_LINK_SCORE_JOB,
} from '../../constants/strings'

export type InsightsActionCardsProps = {
  summary: InsightsSummary | null
}

export function InsightsActionCards({ summary }: InsightsActionCardsProps) {
  const burstStacks = summary?.burst_stacks ?? 0
  const noCurrentScore = summary?.no_current_score ?? 0

  const cards = [
    {
      title: INSIGHTS_ACTION_CULL_BURST,
      value: burstStacks.toLocaleString(),
      description: INSIGHTS_ACTION_CULL_BURST_DESC,
      link: INSIGHTS_LINK_BURST_STACKS,
      badge: 'accent' as const,
    },
    {
      title: INSIGHTS_ACTION_FINISH_PASS,
      value: noCurrentScore.toLocaleString(),
      description: INSIGHTS_ACTION_FINISH_PASS_DESC,
      link: INSIGHTS_LINK_SCORE_JOB,
      badge: 'default' as const,
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {cards.map((card) => (
        <Link key={card.title} to={card.link}>
          <Card hoverable padding="md">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base">{card.title}</CardTitle>
                <Badge variant={card.badge}>{card.value}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-text-secondary">{card.description}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}
