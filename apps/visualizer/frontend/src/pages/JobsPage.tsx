import { useEffect, useState } from 'react'
import { Job } from '../types/job'
import { JobsAPI } from '../services/api'
import { useSocketStore } from '../stores/socketStore'
import { MSG_LOADING, MSG_ERROR_PREFIX, MSG_CONNECTED, MSG_DISCONNECTED, MSG_NO_JOBS } from '../constants/strings'

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { socket, connected, connect, disconnect } = useSocketStore()
  
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])
  
  useEffect(() => {
    let mounted = true
    
    async function fetchJobs() {
      try {
        const fetchedJobs = await JobsAPI.list()
        if (mounted) {
          setJobs(fetchedJobs)
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
    
    fetchJobs()
    return () => { mounted = false }
  }, [])
  
  useEffect(() => {
    if (!socket || !connected) return
    
    socket.on('job_created', (job: Job) => {
      setJobs(prev => [job, ...prev])
    })
    
    socket.on('job_updated', (updatedJob: Job) => {
      setJobs(prev => prev.map(job => 
        job.id === updatedJob.id ? updatedJob : job
      ))
    })
    
    return () => {
      socket.off('job_created')
      socket.off('job_updated')
    }
  }, [socket, connected])
  
  if (loading) {
    return <div className="text-center py-8">{MSG_LOADING}</div>
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">Jobs</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">
            {connected ? MSG_CONNECTED : MSG_DISCONNECTED}
          </span>
        </div>
      </div>
      
      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-800 rounded">
          {MSG_ERROR_PREFIX} {error}
        </div>
      )}
      
      {jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">{MSG_NO_JOBS}</div>
      ) : (
        <div className="space-y-4">
          {jobs.map(job => (
            <div key={job.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{job.type}</h3>
                  <p className="text-sm text-gray-500">{job.id.slice(0, 8)}</p>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  job.status === 'completed' ? 'bg-green-100 text-green-800' :
                  job.status === 'failed' ? 'bg-red-100 text-red-800' :
                  job.status === 'running' ? 'bg-blue-100 text-blue-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {job.status}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                {new Date(job.created_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}