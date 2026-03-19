import { useEffect, useState } from 'react'
import { Stats, JobsAPI, SystemAPI } from '../services/api'
import { Job } from '../types/job'
import { JobsList } from '../components/JobsList'
import {
  MSG_LOADING,
  MSG_ERROR_PREFIX,
  DASHBOARD_CATALOG_IMAGES,
  DASHBOARD_INSTAGRAM_IMAGES,
  DASHBOARD_POSTED,
  DASHBOARD_MATCHES,
  DASHBOARD_RECENT_JOBS,
  DASHBOARD_NO_JOBS,
} from '../constants/strings'

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true

    async function fetchData() {
      try {
        const [statsData, jobsData] = await Promise.all([
          SystemAPI.stats(),
          JobsAPI.list(),
        ])
        if (mounted) {
          setStats(statsData)
          setJobs(jobsData.slice(0, 5))
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    fetchData()
    return () => { mounted = false }
  }, [])

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{MSG_LOADING}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{MSG_ERROR_PREFIX} {error}</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
      
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label={DASHBOARD_CATALOG_IMAGES}
            value={stats.catalog_images}
            color="blue"
          />
          <StatCard
            label={DASHBOARD_INSTAGRAM_IMAGES}
            value={stats.instagram_images}
            color="purple"
          />
          <StatCard
            label={DASHBOARD_POSTED}
            value={stats.posted_to_instagram}
            color="green"
          />
          <StatCard
            label={DASHBOARD_MATCHES}
            value={stats.matches_found}
            color="yellow"
          />
        </div>
      )}

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {DASHBOARD_RECENT_JOBS}
        </h3>
        {jobs.length === 0 ? (
          <p className="text-gray-500">{DASHBOARD_NO_JOBS}</p>
        ) : (
          <JobsList jobs={jobs} />
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  }

  return (
    <div className={`rounded-lg border p-4 ${colorClasses[color]}`}>
      <p className="text-sm font-medium">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  )
}