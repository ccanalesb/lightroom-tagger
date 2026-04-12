import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card'
import {
  INSIGHTS_QUICK_ANALYTICS_DESC,
  INSIGHTS_QUICK_ANALYTICS_TITLE,
  INSIGHTS_QUICK_IDENTITY_DESC,
  INSIGHTS_QUICK_IDENTITY_TITLE,
  INSIGHTS_QUICK_PROCESSING_DESC,
  INSIGHTS_QUICK_PROCESSING_TITLE,
} from '../../constants/strings'

export function InsightsQuickNav() {
  const links = [
    {
      to: '/analytics',
      title: INSIGHTS_QUICK_ANALYTICS_TITLE,
      desc: INSIGHTS_QUICK_ANALYTICS_DESC,
    },
    {
      to: '/identity',
      title: INSIGHTS_QUICK_IDENTITY_TITLE,
      desc: INSIGHTS_QUICK_IDENTITY_DESC,
    },
    {
      to: '/processing',
      title: INSIGHTS_QUICK_PROCESSING_TITLE,
      desc: INSIGHTS_QUICK_PROCESSING_DESC,
    },
  ] as const

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {links.map((item) => (
        <Link key={item.to} to={item.to}>
          <Card hoverable padding="md">
            <CardHeader>
              <CardTitle className="text-base">{item.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-text-secondary">{item.desc}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}
