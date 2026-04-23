import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
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
  JOB_DETAILS_LOGS_TRUNCATED_HEADER,
  JOB_DETAILS_LOGS_SHOW_ALL,
  JOB_DETAILS_LOGS_SHOW_ALL_LOADING,
  JOB_DETAILS_LOADING_ARIA,
  JOB_DETAILS_FETCH_ERROR,
  JOB_DETAILS_METADATA,
  JOB_DETAILS_METADATA_COLLAPSE,
  JOB_DETAILS_METADATA_SHOW_ALL,
  JOB_DETAILS_METADATA_TRUNCATED_HEADER,
  JOB_DETAILS_PROGRESS,
  JOB_DETAILS_RESULT,
  JOB_DETAILS_RESULT_COLLAPSE,
  JOB_DETAILS_RESULT_SHOW_ALL,
  JOB_DETAILS_RESULT_TRUNCATED_HEADER,
  JOB_DETAILS_TITLE,
  MODAL_CLOSE,
  STATUS_LABELS,
} from '../../constants/strings';
import { ErrorBoundary, useQuery } from '../../data';
import { JobsAPI } from '../../services/api';
import { useSocketStore } from '../../stores/socketStore';
import type { Job } from '../../types/job';
import { formatDateTime } from '../../utils/date';
import { Badge } from '../ui/badges';
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

function SkeletonLine({ widthClass }: { widthClass: string }) {
  return <div className={`h-3 ${widthClass} rounded-base bg-surface animate-pulse`} />;
}

function SkeletonSection({ label }: { label: string }) {
  return (
    <div
      className="space-y-2 rounded-base border border-border p-3"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="h-4 w-32 rounded-base bg-surface animate-pulse" />
      <SkeletonLine widthClass="w-full" />
      <SkeletonLine widthClass="w-5/6" />
      <SkeletonLine widthClass="w-2/3" />
    </div>
  );
}

function JobDetailIdentityGrid({ job }: { job: Job }) {
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div>
        <span className="text-text-secondary">ID:</span>
        <p className="font-mono text-xs break-all text-text">{job.id}</p>
      </div>
      <div>
        <span className="text-text-secondary">Type:</span>
        <p className="font-medium text-text">{job.type}</p>
      </div>
      <div>
        <span className="text-text-secondary">Status:</span>
        <div className="mt-1">
          <Badge variant={statusToBadgeVariant(job.status)}>
            {STATUS_LABELS[job.status] ?? job.status}
          </Badge>
        </div>
      </div>
      <div>
        <span className="text-text-secondary">Created:</span>
        <p className="text-text">{formatDateTime(job.created_at)}</p>
      </div>
    </div>
  );
}

function JobDetailProgress({ job }: { job: Job }) {
  if (job.progress === undefined) return null;

  const pct = job.progress <= 1 ? Math.round(job.progress * 100) : Math.round(job.progress);

  return (
    <div className="mt-4">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-text-secondary">{JOB_DETAILS_PROGRESS}</span>
        <span className="font-medium text-text">{pct}%</span>
      </div>
      <div className="w-full bg-surface rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${progressFillClass(job.status)}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}

function JobDetailModalSuspenseFallback({ job }: { job: Job }) {
  return (
    <>
      <JobDetailIdentityGrid job={job} />
      <JobDetailProgress job={job} />
      <div
        className="rounded-base border border-border bg-accent-light p-3"
        role="status"
        aria-label={JOB_DETAILS_LOADING_ARIA}
      >
        <SkeletonLine widthClass="w-24" />
        <div className="mt-2 h-3 w-2/3 rounded-base bg-accent/20 animate-pulse" />
      </div>
      <SkeletonSection label={JOB_DETAILS_LOADING_ARIA} />
      <SkeletonSection label={JOB_DETAILS_LOADING_ARIA} />
    </>
  );
}

interface JobDetailModalProps {
  job: Job;
  onClose: () => void;
  onJobUpdate?: (updatedJob: Job) => void;
}

function JobDetailModalBody({ job, onClose, onJobUpdate }: JobDetailModalProps) {
  const queried = useQuery(
    ['jobs.detail', job.id] as const,
    () => JobsAPI.get(job.id, { logs_limit: 20 }),
  );

  const [localJob, setLocalJob] = useState<Job>(() => queried);
  const [retrying, setRetrying] = useState(false);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [expandingLogs, setExpandingLogs] = useState(false);
  const [metadataExpanded, setMetadataExpanded] = useState(false);
  const [resultExpanded, setResultExpanded] = useState(false);
  const logsExpandedRef = useRef(false);
  useEffect(() => {
    logsExpandedRef.current = logsExpanded;
  }, [logsExpanded]);
  const socket = useSocketStore((state) => state.socket);

  useEffect(() => {
    setLocalJob(queried);
    setLogsExpanded(false);
    setExpandingLogs(false);
    setMetadataExpanded(false);
    setResultExpanded(false);
  }, [queried]);

  useEffect(() => {
    setLocalJob((prev) => {
      if (prev.id !== job.id) return prev;
      if (
        prev.status === job.status &&
        prev.progress === job.progress &&
        prev.current_step === job.current_step
      ) {
        return prev;
      }
      return { ...prev, status: job.status, progress: job.progress, current_step: job.current_step };
    });
  }, [job.id, job.status, job.progress, job.current_step]);

  useEffect(() => {
    if (!socket) return;

    socket.emit('subscribe_job', { job_id: job.id });

    const handleJobUpdate = (updatedJob: Job) => {
      if (updatedJob.id !== job.id) return;
      if (logsExpandedRef.current) {
        setLocalJob(updatedJob);
      } else {
        setLocalJob((prev) => ({
          ...updatedJob,
          logs: prev.logs,
          logs_total: updatedJob.logs_total ?? updatedJob.logs?.length ?? prev.logs_total,
        }));
      }
      onJobUpdate?.(updatedJob);
    };

    socket.on('job_updated', handleJobUpdate);

    return () => {
      socket.emit('unsubscribe_job', { job_id: job.id });
      socket.off('job_updated', handleJobUpdate);
    };
  }, [socket, job.id, onJobUpdate]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const displayJob = localJob;

  const JSON_PREVIEW_LINES = 20;

  const metadataPreview = useMemo(() => {
    if (!displayJob.metadata || Object.keys(displayJob.metadata).length === 0) {
      return null;
    }
    const full = JSON.stringify(displayJob.metadata, null, 2);
    const lines = full.split('\n');
    const truncated = lines.length > JSON_PREVIEW_LINES;
    return {
      full,
      previewText: truncated
        ? `${lines.slice(0, JSON_PREVIEW_LINES).join('\n')}\n…`
        : full,
      totalLines: lines.length,
      previewLines: Math.min(lines.length, JSON_PREVIEW_LINES),
      truncated,
    };
  }, [displayJob.metadata]);

  const resultPreview = useMemo(() => {
    if (!displayJob.result) return null;
    const full = JSON.stringify(displayJob.result, null, 2);
    const lines = full.split('\n');
    const truncated = lines.length > JSON_PREVIEW_LINES;
    return {
      full,
      previewText: truncated
        ? `${lines.slice(0, JSON_PREVIEW_LINES).join('\n')}\n…`
        : full,
      totalLines: lines.length,
      previewLines: Math.min(lines.length, JSON_PREVIEW_LINES),
      truncated,
    };
  }, [displayJob.result]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const updated = await JobsAPI.retry(displayJob.id);
      setLocalJob(updated);
      onJobUpdate?.(updated);
    } catch (err) {
      console.error('Retry failed:', err);
    } finally {
      setRetrying(false);
    }
  };

  const handleExpandLogs = async () => {
    if (logsExpanded || expandingLogs) return;
    setExpandingLogs(true);
    try {
      const fullJob = await JobsAPI.get(displayJob.id, { logs_limit: 0 });
      setLocalJob(fullJob);
      setLogsExpanded(true);
    } catch (err) {
      console.error('Failed to load full logs:', err);
    } finally {
      setExpandingLogs(false);
    }
  };

  return (
    <>
      <JobDetailIdentityGrid job={displayJob} />
      <JobDetailProgress job={displayJob} />

      {displayJob.current_step ? (
        <div className="rounded-base border border-border bg-accent-light p-3">
          <span className="text-sm font-medium text-accent">{JOB_DETAILS_CURRENT_STEP}:</span>
          <p className="text-sm text-text mt-1">{displayJob.current_step}</p>
        </div>
      ) : null}

      {metadataPreview ? (
        <div className="rounded-base border border-border p-3">
          <div className="flex flex-row items-center justify-between gap-2 mb-2">
            <h4 className="font-medium text-sm text-text">
              {metadataPreview.truncated && !metadataExpanded
                ? JOB_DETAILS_METADATA_TRUNCATED_HEADER(
                    metadataPreview.previewLines,
                    metadataPreview.totalLines,
                  )
                : JOB_DETAILS_METADATA}
            </h4>
            {metadataPreview.truncated && (
              <Button variant="ghost" size="sm" onClick={() => setMetadataExpanded((v) => !v)}>
                {metadataExpanded
                  ? JOB_DETAILS_METADATA_COLLAPSE
                  : JOB_DETAILS_METADATA_SHOW_ALL(metadataPreview.totalLines)}
              </Button>
            )}
          </div>
          <pre className="text-xs bg-surface p-2 rounded-base max-h-96 overflow-auto whitespace-pre-wrap break-words text-text border border-border">
            {metadataExpanded ? metadataPreview.full : metadataPreview.previewText}
          </pre>
        </div>
      ) : null}

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
            {!(displayJob.metadata?.provider_id || displayJob.result?.provider_id) &&
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

      {resultPreview && (
        <div className="rounded-base border border-border border-success/40 bg-surface p-3">
          <div className="flex flex-row items-center justify-between gap-2 mb-2">
            <h4 className="font-medium text-sm text-success">
              {resultPreview.truncated && !resultExpanded
                ? JOB_DETAILS_RESULT_TRUNCATED_HEADER(
                    resultPreview.previewLines,
                    resultPreview.totalLines,
                  )
                : JOB_DETAILS_RESULT}
            </h4>
            {resultPreview.truncated && (
              <Button variant="ghost" size="sm" onClick={() => setResultExpanded((v) => !v)}>
                {resultExpanded
                  ? JOB_DETAILS_RESULT_COLLAPSE
                  : JOB_DETAILS_RESULT_SHOW_ALL(resultPreview.totalLines)}
              </Button>
            )}
          </div>
          <pre className="text-xs bg-bg p-2 rounded-base max-h-96 overflow-auto whitespace-pre-wrap break-words text-text border border-border">
            {resultExpanded ? resultPreview.full : resultPreview.previewText}
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
              <Badge {...errorSeverityBadgeProps(displayJob.error_severity)}>
                {ERROR_SEVERITY_LABELS[displayJob.error_severity]}
              </Badge>
            )}
          </div>
          <p className="text-sm text-error font-mono">{displayJob.error}</p>
        </div>
      )}

      {(displayJob.status === 'failed' || displayJob.status === 'cancelled') && (
        <Button variant="primary" size="sm" onClick={handleRetry} disabled={retrying} type="button">
          {retrying ? 'Retrying...' : 'Retry this job'}
        </Button>
      )}

      {displayJob.logs && displayJob.logs.length > 0 ? (() => {
        const logsShown = displayJob.logs.length;
        const logsTotal = displayJob.logs_total ?? logsShown;
        const isTruncated = logsTotal > logsShown;
        return (
          <div className="rounded-base border border-border p-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium text-sm text-text">
                {isTruncated ? JOB_DETAILS_LOGS_TRUNCATED_HEADER(logsShown, logsTotal) : JOB_DETAILS_LOGS}
              </h4>
              {isTruncated && !logsExpanded && (
                <Button
                  variant="ghost"
                  size="sm"
                  type="button"
                  onClick={() => {
                    void handleExpandLogs();
                  }}
                  disabled={expandingLogs}
                >
                  {expandingLogs ? JOB_DETAILS_LOGS_SHOW_ALL_LOADING : JOB_DETAILS_LOGS_SHOW_ALL(logsTotal)}
                </Button>
              )}
            </div>
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
        );
      })() : null}
    </>
  );
}

export function JobDetailModal({ job, onClose, onJobUpdate }: JobDetailModalProps) {
  const backdropRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = backdropRef.current;
    if (!el) return;
    const handler = (e: Event) => {
      if (e.target === el) e.preventDefault();
    };
    el.addEventListener('wheel', handler, { passive: false });
    el.addEventListener('touchmove', handler, { passive: false });
    return () => {
      el.removeEventListener('wheel', handler);
      el.removeEventListener('touchmove', handler);
    };
  }, []);

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 overscroll-contain"
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
            <ErrorBoundary
              resetKeys={[job.id]}
              fallback={({ error }) => (
                <>
                  <JobDetailIdentityGrid job={job} />
                  <JobDetailProgress job={job} />
                  <div
                    className="rounded-base border border-error/50 bg-red-50 dark:bg-red-950/30 p-3"
                    role="alert"
                  >
                    <p className="text-sm text-error">{JOB_DETAILS_FETCH_ERROR}</p>
                    <p className="text-xs text-text-secondary mt-1">{error.message}</p>
                  </div>
                </>
              )}
            >
              <Suspense fallback={<JobDetailModalSuspenseFallback job={job} />}>
                <JobDetailModalBody key={job.id} job={job} onClose={onClose} onJobUpdate={onJobUpdate} />
              </Suspense>
            </ErrorBoundary>
          </div>
        </Card>
      </div>
    </div>
  );
}
