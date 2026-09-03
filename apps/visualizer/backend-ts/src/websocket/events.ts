/**
 * Socket.IO wiring. Port of `websocket/events.py` plus the emit call sites in
 * `app.py` and `api/jobs.py`.
 *
 * The server instance is held in a module-level slot rather than threaded through
 * every caller. Emits happen from three places — the jobs routes, the orphan
 * recovery pass and the processor's progress callback — and the alternative was
 * Python's `from app import socketio` late import in each of them.
 *
 * `emitJobEvent` is a no-op before the server is attached, which is what makes the
 * routes testable without a live socket: the Python code guarded every emit with
 * `if socketio:` for the same reason.
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
     * This event re-broadcasts the request to the asking client so the UI can show
     * "cancelling…" immediately; it deliberately does not touch the database,
     * because the REST route owns the state transition.
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
