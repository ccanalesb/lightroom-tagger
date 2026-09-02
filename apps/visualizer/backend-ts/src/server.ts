/**
 * Server entrypoint. Port of the `__main__` block in `app.py`.
 *
 * Binds 5001 by default (see config): macOS AirPlay Receiver owns :5000 and
 * answers requests there, which masquerades as a broken backend.
 */
import { serve } from '@hono/node-server';
import { Server as SocketIOServer } from 'socket.io';
import { config } from './config.js';
import { createApp } from './app.js';

const app = createApp();

const server = serve({ fetch: app.fetch, hostname: config.HOST, port: config.PORT }, (info) => {
  process.stderr.write(`backend listening on http://${config.HOST}:${info.port}\n`);
});

/**
 * SocketIO shares the HTTP server. Job progress is pushed over this channel —
 * the frontend must never poll for job status.
 */
export const io = new SocketIOServer(server as never, {
  cors: { origin: config.FRONTEND_ORIGINS, credentials: true },
});

const shutdown = (signal: string) => {
  process.stderr.write(`\n${signal} received, shutting down\n`);
  io.close();
  server.close(() => process.exit(0));
};
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
