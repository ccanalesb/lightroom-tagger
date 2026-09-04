/**
 * Pure job status transitions — no HTTP dependencies.
 *
 * Kept separate from the route because the transition rules are the part with
 * edges: cancelling an already-cancelled job is a *noop*, not an error, but it
 * still has to re-signal the runner, because the first cancel may have landed
 * while the worker was mid-step and never took effect.
 */
import type { Db } from '../db/connection.js';
import {
  addJobLog,
  getJob,
  updateJobField,
  updateJobStatus,
  type JobRow,
} from '../db/jobs/jobs.js';

export const CANCELLABLE_STATUSES = new Set(['running', 'pending']);
export const TERMINAL_CANCEL_STATUSES = new Set(['cancelled', 'completed', 'failed']);
export const RETRYABLE_STATUSES = new Set(['failed', 'cancelled']);

const CANCEL_LOG_MESSAGE = 'Cancel requested via API';
const RETRY_LOG_MESSAGE = 'Job queued for retry';

export type TransitionEdge = 'cancelled' | 'noop' | 'invalid' | 'retried';

export interface Outcome {
  edge: TransitionEdge;
  job: JobRow | null;
  reason?: string | null;
  shouldSignalCancel?: boolean;
}

export function canCancel(job: JobRow): boolean {
  return CANCELLABLE_STATUSES.has(job.status);
}

export function canRetry(job: JobRow): boolean {
  return RETRYABLE_STATUSES.has(job.status);
}

export function transitionCancel(db: Db, jobId: string): Outcome {
  const job = getJob(db, jobId);
  if (!job) return { edge: 'invalid', job: null, reason: 'Job not found' };

  const { status } = job;

  if (CANCELLABLE_STATUSES.has(status)) {
    updateJobStatus(db, jobId, 'cancelled');
    addJobLog(db, jobId, 'info', CANCEL_LOG_MESSAGE);
    return {
      edge: 'cancelled',
      job: getJob(db, jobId),
      // Only a *running* job has a worker to interrupt.
      shouldSignalCancel: status === 'running',
    };
  }

  if (TERMINAL_CANCEL_STATUSES.has(status)) {
    return {
      edge: 'noop',
      job,
      reason: `Job is already ${status}`,
      // Re-signal an already-cancelled job: the earlier cancel may have been
      // recorded while the worker was mid-step and never actually stopped it.
      shouldSignalCancel: status === 'cancelled',
    };
  }

  // Unreachable for the known status set, since cancellable plus terminal covers
  // all five. Kept as a guard against a status the DB grows later.
  return { edge: 'invalid', job, reason: `Cannot cancel job in status '${status}'` };
}

export function transitionRetry(db: Db, jobId: string): Outcome {
  const job = getJob(db, jobId);
  if (!job) return { edge: 'invalid', job: null, reason: 'Job not found' };

  if (!RETRYABLE_STATUSES.has(job.status)) {
    return { edge: 'invalid', job, reason: 'Can only retry failed or cancelled jobs' };
  }

  // Reset to pending and clear the previous failure, so the UI does not show a
  // stale error next to a queued job. `metadata` is deliberately preserved —
  // it carries the checkpoint the retry resumes from.
  updateJobStatus(db, jobId, 'pending', { progress: 0, currentStep: null });
  updateJobField(db, jobId, 'error', null);
  db.prepare('UPDATE jobs SET error_severity = NULL WHERE id = ?').run(jobId);
  updateJobField(db, jobId, 'result', null);
  addJobLog(db, jobId, 'info', RETRY_LOG_MESSAGE);

  return { edge: 'retried', job: getJob(db, jobId) };
}
