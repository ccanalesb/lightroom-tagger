/**
 * Cooperative event-loop yields for long synchronous job loops.
 *
 * See ADR-0018: handlers stay on the main thread but must yield so HTTP and
 * cancellation requests can be served between units of work.
 */
import type { Db } from '../db/connection.js';

/** Default elapsed time between yields (ms). */
export const EVENT_LOOP_YIELD_BUDGET_MS = 50;

export interface EventLoopYieldState {
  lastYieldAt: number;
}

/** Fresh yield budget for one pass over a blocking loop. */
export function createEventLoopYieldState(): EventLoopYieldState {
  return { lastYieldAt: Date.now() };
}

/**
 * Poll cancellation and yield to the event loop when the budget has elapsed.
 *
 * Returns `true` when `isCancelled` is already true or becomes true after the
 * yield. Uses `setImmediate` — not a microtask — so I/O callbacks in the poll
 * phase can run.
 *
 * Throws when `db` is inside `libraryWrite`: yielding there would hold the write
 * lock across the yield.
 */
export async function pollCancelAndYield(
  db: Db,
  isCancelled: () => boolean | Promise<boolean>,
  state: EventLoopYieldState,
  budgetMs = EVENT_LOOP_YIELD_BUDGET_MS,
): Promise<boolean> {
  if (await isCancelled()) return true;
  const now = Date.now();
  if (now - state.lastYieldAt < budgetMs) return false;
  if (db.inTransaction) {
    throw new Error('pollCancelAndYield: cannot yield while library.db transaction is open');
  }
  state.lastYieldAt = now;
  await new Promise<void>((resolve) => setImmediate(resolve));
  return await isCancelled();
}
