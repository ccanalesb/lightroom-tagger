import { useEffect, useState } from 'react'

import type { Job } from '../types/job'

import { Stats, CacheStatus, JobsAPI, SystemAPI } from '../services/api'
import { JobsList } from '../components/jobs/JobsList'
import { CacheStatusCard } from '../components/matching/CacheStatusCard'
import { StatCard } from '../components/ui/StatCard'
import { PageLoading, PageError, EmptyState } from '../components/ui/page-states'
import {
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
  const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null)
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

    async function fetchCacheStatus() {
      try {
        const data = await SystemAPI.cacheStatus()
        if (mounted) setCacheStatus(data)
      } catch {
        // Non-critical -- dashboard still works without cache status
      }
    }

    fetchData()
    fetchCacheStatus()
    return () => { mounted = false }
  }, [])

  if (loading) return <PageLoading />
  if (error) return <PageError message={error} />

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

      {cacheStatus && <CacheStatusCard cacheStatus={cacheStatus} />}

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {DASHBOARD_RECENT_JOBS}
        </h3>
        {jobs.length === 0 ? (
          <EmptyState message={DASHBOARD_NO_JOBS} />
        ) : (
          <JobsList jobs={jobs} />
        )}
      </div>
    </div>
  )
}
