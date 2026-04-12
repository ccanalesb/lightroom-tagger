import { useState, useEffect, type Dispatch, type SetStateAction } from 'react';
import type { MouseEvent } from 'react';
import { JobsAPI } from '../../services/api';
import type { Job } from '../../types/job';
import { JobDetailModal } from '../jobs/JobDetailModal';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

function getStatusVariant(status: Job['status']): 'default' | 'success' | 'warning' | 'error' | 'accent' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    case 'running':
      return 'accent';
    case 'cancelled':
      return 'warning';
    case 'pending':
      return 'default';
  }
}

function progressWidthPercent(job: Job): number {
  const p = job.progress ?? 0;
  return Math.min(100, p <= 1 ? p * 100 : p);
}

export interface JobQueueTabProps {
  jobs: Job[];
  setJobs: Dispatch<SetStateAction<Job[]>>;
  jobsLoading: boolean;
  connected: boolean;
  onRefreshJobs: () => void | Promise<void>;
}

export function JobQueueTab({
  jobs,
  setJobs,
  jobsLoading,
  connected,
  onRefreshJobs,
}: JobQueueTabProps) {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const cancelJob = async (jobId: string, e: MouseEvent) => {
    e.stopPropagation();
    setCancellingId(jobId);
    try {
      await JobsAPI.cancel(jobId);
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: 'cancelled' as const } : j)),
      );
    } catch (err) {
      alert(`Failed to cancel job: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setCancellingId(null);
    }
  };

  useEffect(() => {
    setSelectedJob((prev) => {
      if (!prev) return null;
      const match = jobs.find((j) => j.id === prev.id);
      return match ?? prev;
    });
  }, [jobs]);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-success' : 'bg-error'}`} />
          <span className="text-sm text-text-secondary">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void onRefreshJobs();
          }}
        >
          Refresh
        </Button>
      </div>

      {jobsLoading ? (
        <Card padding="lg">
          <div className="text-center py-8 text-text-secondary">Loading jobs...</div>
        </Card>
      ) : jobs.length === 0 ? (
        <Card padding="lg">
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-text-tertiary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">No jobs</h3>
            <p className="mt-1 text-sm text-text-secondary">
              Start a matching or description job to see it here
            </p>
          </div>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface">
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Progress
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className="hover:bg-surface cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-text">{job.type}</div>
                      <div className="text-xs text-text-tertiary font-mono">{job.id.slice(0, 8)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-text-secondary whitespace-nowrap">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      {job.status === 'running' && (
                        <div className="w-full bg-surface rounded-full h-2">
                          <div
                            className="bg-accent h-2 rounded-full transition-all duration-300"
                            style={{ width: `${progressWidthPercent(job)}%` }}
                          />
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right text-sm">
                      {(job.status === 'pending' || job.status === 'running') && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={(e) => cancelJob(job.id, e)}
                          disabled={cancellingId === job.id}
                          type="button"
                        >
                          {cancellingId === job.id ? 'Cancelling...' : 'Cancel'}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {selectedJob && (
        <JobDetailModal job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  );
}
