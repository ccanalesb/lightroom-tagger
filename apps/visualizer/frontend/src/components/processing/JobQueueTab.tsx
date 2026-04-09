import { useEffect, useState, useCallback } from 'react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { JobsAPI } from '../../services/api';
import type { Job } from '../../types/job';

export function JobQueueTab() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await JobsAPI.list();
      setJobs(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="secondary" size="sm" onClick={loadJobs}>
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </Button>
      </div>

      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-border">
              <tr className="bg-surface">
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase">Created</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase">Progress</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-surface transition-colors">
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-text">{job.type}</div>
                    <div className="text-xs text-text-tertiary">{job.id.substring(0, 8)}</div>
                  </td>
                  <td className="px-6 py-4">
                    <Badge
                      variant={
                        job.status === 'completed' ? 'success' :
                        job.status === 'failed' ? 'error' :
                        job.status === 'running' ? 'accent' : 'default'
                      }
                    >
                      {job.status}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-text-secondary">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    {job.status === 'running' && (
                      <div className="w-full bg-surface rounded-full h-2">
                        <div
                          className="bg-accent h-2 rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, job.progress ?? 0)}%` }}
                        />
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {jobs.length === 0 && !loading && (
        <Card padding="lg">
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">No jobs</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Start a matching or description job to see it here
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
