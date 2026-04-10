import { useEffect, useState } from 'react';
import {
  JOB_CONFIG_DATE_WINDOW,
  JOB_CONFIG_METHOD,
  JOB_CONFIG_THRESHOLD,
  JOB_CONFIG_VISION_MODEL,
  JOB_CONFIG_WEIGHTS,
  JOB_DETAILS_CURRENT_STEP,
  JOB_DETAILS_ERROR,
  ERROR_SEVERITY_LABELS,
  JOB_DETAILS_LOGS,
  JOB_DETAILS_METADATA,
  JOB_DETAILS_PROGRESS,
  JOB_DETAILS_RESULT,
  JOB_DETAILS_TITLE,
  MODAL_CLOSE,
  STATUS_LABELS,
} from '../../constants/strings';
import { JobsAPI } from '../../services/api';
import { useSocketStore } from '../../stores/socketStore';
import type { Job } from '../../types/job';
import { formatDateTime } from '../../utils/date';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card, CardTitle } from '../ui/Card';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'accent';

function statusToBadgeVariant(status: Job['status']): BadgeVariant {
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

function errorSeverityBadgeProps(severity: 'warning' | 'error' | 'critical'): {
  variant: BadgeVariant;
  className: string;
} {
  if (severity === 'warning') {
    return { variant: 'warning', className: '' };
  }
  if (severity === 'critical') {
    return { variant: 'error', className: 'ring-2 ring-error' };
  }
  return { variant: 'error', className: '' };
}

function progressFillClass(status: Job['status']): string {
  switch (status) {
    case 'completed':
      return 'bg-success';
    case 'failed':
      return 'bg-error';
    case 'running':
    case 'pending':
    case 'cancelled':
      return 'bg-accent';
  }
}

interface JobDetailModalProps {
  job: Job;
  onClose: () => void;
  onJobUpdate?: (updatedJob: Job) => void;
}

export function JobDetailModal({ job, onClose, onJobUpdate }: JobDetailModalProps) {
  const [localJob, setLocalJob] = useState<Job>(job);
  const socket = useSocketStore((state) => state.socket);

  useEffect(() => {
    JobsAPI.get(job.id)
      .then((freshJob) => {
        setLocalJob(freshJob);
      })
      .catch((err) => {
        console.error('Failed to fetch job details:', err);
      });
  }, [job.id]);

  useEffect(() => {
    if (!socket) return;

    socket.emit('subscribe_job', { job_id: job.id });

    const handleJobUpdate = (updatedJob: Job) => {
      if (updatedJob.id === job.id) {
        setLocalJob(updatedJob);
        onJobUpdate?.(updatedJob);
      }
    };

    socket.on('job_updated', handleJobUpdate);

    return () => {
      socket.emit('unsubscribe_job', { job_id: job.id });
      socket.off('job_updated', handleJobUpdate);
    };
  }, [socket, job.id, onJobUpdate]);

  const displayJob = localJob.id === job.id ? localJob : job;

  const renderProgress = () => {
    if (displayJob.progress === undefined) return null;

    const pct =
      displayJob.progress <= 1 ? Math.round(displayJob.progress * 100) : Math.round(displayJob.progress);

    return (
      <div className="mt-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-text-secondary">{JOB_DETAILS_PROGRESS}</span>
          <span className="font-medium text-text">{pct}%</span>
        </div>
        <div className="w-full bg-surface rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${progressFillClass(displayJob.status)}`}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
      role="presentation"
    >
      <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <Card padding="none" className="max-h-[80vh] flex flex-col overflow-hidden shadow-deep">
          <div className="flex justify-between items-center px-4 py-3 border-b border-border shrink-0">
            <CardTitle>{JOB_DETAILS_TITLE}</CardTitle>
            <Button variant="ghost" size="sm" onClick={onClose} type="button">
              {MODAL_CLOSE}
            </Button>
          </div>

          <div className="p-4 space-y-4 overflow-y-auto">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-text-secondary">ID:</span>
                <p className="font-mono text-xs break-all text-text">{displayJob.id}</p>
              </div>
              <div>
                <span className="text-text-secondary">Type:</span>
                <p className="font-medium text-text">{displayJob.type}</p>
              </div>
              <div>
                <span className="text-text-secondary">Status:</span>
                <div className="mt-1">
                  <Badge variant={statusToBadgeVariant(displayJob.status)}>
                    {STATUS_LABELS[displayJob.status] ?? displayJob.status}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="text-text-secondary">Created:</span>
                <p className="text-text">{formatDateTime(displayJob.created_at)}</p>
              </div>
            </div>

            {renderProgress()}

            {displayJob.current_step && (
              <div className="rounded-base border border-border bg-accent-light p-3">
                <span className="text-sm font-medium text-accent">{JOB_DETAILS_CURRENT_STEP}:</span>
                <p className="text-sm text-text mt-1">{displayJob.current_step}</p>
              </div>
            )}

            {displayJob.metadata && Object.keys(displayJob.metadata).length > 0 && (
              <div className="rounded-base border border-border p-3">
                <h4 className="font-medium text-sm mb-2 text-text">{JOB_DETAILS_METADATA}</h4>
                <pre className="text-xs bg-surface p-2 rounded-base overflow-x-auto text-text border border-border">
                  {JSON.stringify(displayJob.metadata, null, 2)}
                </pre>
              </div>
            )}

            {(displayJob.metadata?.method || displayJob.result?.method) && (
              <div className="rounded-base border border-border bg-surface p-3">
                <h4 className="font-medium text-sm mb-2 text-text">Configuration</h4>
                <div className="text-sm space-y-1 text-text">
                  {(displayJob.metadata?.method || displayJob.result?.method) && (
                    <div className="flex justify-between gap-2">
                      <span className="text-text-secondary">{JOB_CONFIG_METHOD}:</span>
                      <span className="font-medium text-right">
                        {displayJob.metadata?.method || displayJob.result?.method}
                      </span>
                    </div>
                  )}
                  {(displayJob.metadata?.date_window_days || displayJob.result?.date_window_days) && (
                    <div className="flex justify-between gap-2">
                      <span className="text-text-secondary">{JOB_CONFIG_DATE_WINDOW}:</span>
                      <span className="font-medium">
                        {displayJob.metadata?.date_window_days || displayJob.result?.date_window_days} days
                      </span>
                    </div>
                  )}
                  {(displayJob.metadata?.provider_id || displayJob.result?.provider_id) && (
                    <div className="flex justify-between gap-2">
                      <span className="text-text-secondary">Provider:</span>
                      <span className="font-medium font-mono text-right">
                        {displayJob.metadata?.provider_id || displayJob.result?.provider_id}
                        {(displayJob.metadata?.provider_model || displayJob.result?.provider_model) &&
                          ` / ${displayJob.metadata?.provider_model || displayJob.result?.provider_model}`}
                      </span>
                    </div>
                  )}
                  {!(
                    displayJob.metadata?.provider_id || displayJob.result?.provider_id
                  ) &&
                    (displayJob.metadata?.vision_model || displayJob.result?.vision_model) && (
                      <div className="flex justify-between gap-2">
                        <span className="text-text-secondary">{JOB_CONFIG_VISION_MODEL}:</span>
                        <span className="font-medium font-mono text-right">
                          {displayJob.metadata?.vision_model || displayJob.result?.vision_model}
                        </span>
                      </div>
                    )}
                  {(displayJob.metadata?.threshold || displayJob.result?.threshold) && (
                    <div className="flex justify-between gap-2">
                      <span className="text-text-secondary">{JOB_CONFIG_THRESHOLD}:</span>
                      <span className="font-medium">
                        {displayJob.metadata?.threshold || displayJob.result?.threshold}
                      </span>
                    </div>
                  )}
                  {(displayJob.metadata?.weights || displayJob.result?.weights) && (
                    <div>
                      <span className="text-text-secondary">{JOB_CONFIG_WEIGHTS}:</span>
                      <div className="mt-1 pl-4 text-xs space-y-0.5">
                        <div>
                          pHash:{' '}
                          {(
                            (displayJob.metadata?.weights?.phash ??
                              displayJob.result?.weights?.phash ??
                              0) * 100
                          ).toFixed(0)}
                          %
                        </div>
                        <div>
                          Description:{' '}
                          {(
                            (displayJob.metadata?.weights?.description ??
                              displayJob.result?.weights?.description ??
                              0) * 100
                          ).toFixed(0)}
                          %
                        </div>
                        <div>
                          Vision:{' '}
                          {(
                            (displayJob.metadata?.weights?.vision ??
                              displayJob.result?.weights?.vision ??
                              0) * 100
                          ).toFixed(0)}
                          %
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {displayJob.result && (
              <div className="rounded-base border border-border border-success/40 bg-surface p-3">
                <h4 className="font-medium text-sm mb-2 text-success">{JOB_DETAILS_RESULT}</h4>
                <pre className="text-xs bg-bg p-2 rounded-base overflow-x-auto text-text border border-border">
                  {JSON.stringify(displayJob.result, null, 2)}
                </pre>
              </div>
            )}

            {displayJob.error && (
              <div className="rounded-base border border-error/50 bg-red-50 dark:bg-red-950/30 p-3">
                <div className="flex flex-row items-center justify-between gap-2 mb-2">
                  <h4 className="font-medium text-sm text-error">{JOB_DETAILS_ERROR}</h4>
                  {(displayJob.error_severity === 'warning' ||
                    displayJob.error_severity === 'error' ||
                    displayJob.error_severity === 'critical') && (
                    <Badge
                      {...errorSeverityBadgeProps(displayJob.error_severity)}
                    >
                      {ERROR_SEVERITY_LABELS[displayJob.error_severity]}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-error font-mono">{displayJob.error}</p>
              </div>
            )}

            {displayJob.logs && displayJob.logs.length > 0 && (
              <div className="rounded-base border border-border p-3">
                <h4 className="font-medium text-sm mb-2 text-text">{JOB_DETAILS_LOGS}</h4>
                <div className="bg-surface text-text p-3 rounded-base font-mono text-xs max-h-48 overflow-y-auto border border-border">
                  {displayJob.logs.map((log, idx) => (
                    <div key={idx} className="mb-1">
                      <span className="text-text-tertiary">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <span
                        className={`ml-2 ${
                          log.level === 'error'
                            ? 'text-error'
                            : log.level === 'warning'
                              ? 'text-warning'
                              : 'text-success'
                        }`}
                      >
                        [{log.level}]
                      </span>
                      <span className="ml-2">{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
