/**
 * Socket.IO wiring.
 *
 * Module-level server slot so emits from routes, recovery, and the processor do not
 * need the instance threaded through every caller.
 *
 * `emitJobEvent` is a no-op before attach, so routes are testable without a socket.
 */
import type { Server } from 'socket.io';
import type { Job } from '../api/schemas/jobs.js';

let io: Server | null = null;

/** Attach the Socket.IO server and register its handlers. */
export function registerSocketEvents(server: Server): void {
  io = server;

  server.on('connection', (socket) => {
    socket.emit('connected', { status: 'ok' });

    // Per-job rooms let the frontend subscribe to one job's stream instead of
    // every job's; a batch run emits progress about once a second per job.
    socket.on('subscribe_job', (data: { job_id?: string } | undefined) => {
      const jobId = data?.job_id;
      if (!jobId) return;
      void socket.join(`job_${jobId}`);
      socket.emit('subscribed', { job_id: jobId });
    });

    socket.on('unsubscribe_job', (data: { job_id?: string } | undefined) => {
      const jobId = data?.job_id;
      if (!jobId) return;
      void socket.leave(`job_${jobId}`);
      socket.emit('unsubscribed', { job_id: jobId });
    });

    /**
     * Acknowledge only — cancellation goes through `DELETE /api/jobs/{id}`.
     *
     * Re-broadcasts to the asking client so the UI can show "cancelling…" immediately;
     * does not touch the database — the REST route owns the state transition.
     */
    socket.on('cancel_job', (data: { job_id?: string } | undefined) => {
      socket.emit('job_cancel_requested', { job_id: data?.job_id });
    });
  });
}

/** Broadcast a job payload, or do nothing when no socket server is attached. */
export function emitJobEvent(event: 'job_created' | 'job_updated', payload: Job): void {
  io?.emit(event, payload);
}

/** Broadcast the ids re-queued by the restart recovery pass. */
export function emitJobsRecovered(jobIds: readonly string[]): void {
  io?.emit('jobs_recovered', { job_ids: [...jobIds] });
}

/** Test and shutdown seam: drop the server reference. */
export function resetSocketServer(): void {
  io = null;
}
