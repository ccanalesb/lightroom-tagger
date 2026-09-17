# ADR-0018: Job handlers stay on the event loop and yield cooperatively

**Status:** Accepted
**Date:** 2026-09-17

## Context

Job handlers are awaited inline by the job processor on the main event loop, and
the hottest handlers iterate tens of thousands of times with no `await` in the
loop body. While one of those runs, the Node event loop never reaches its poll
phase, so the HTTP server accepts connections but never answers them
([#310](https://github.com/ccanalesb/lightroom-tagger/issues/310)). Observed
against a real ~43k-image catalog: `/api/status` times out for the duration, and
because `DELETE /api/jobs/{id}` is never served either, a running job cannot be
cancelled from the UI.

Three job types are responsible. `batch_catalog_similarity` is the worst — a
synchronous loop over ~43k CLIP seeds, each running a sqlite-vec KNN.
`batch_stack_detect` is a synchronous loop of similar length, and `catalog_sync`
becomes one when catalog drift is large. The remaining handlers await a provider
HTTP call per item and already yield naturally.

Two facts shaped the decision and are easy to get wrong from a reading of the
code:

- **Cancellation was never broken.** `transitionCancel` persists
  `status = 'cancelled'` to `visualizer.db`, and `isCancelled` falls back to
  reading that row when its in-memory flag is unset, so the cancel path already
  crosses connection boundaries. The only failure was that the HTTP request
  carrying the cancel could not be served. Restoring responsiveness restores
  cancellation with no new signalling channel.
- **The migration PR's description claimed handlers run "on a `worker_threads`
  runner." They never have.** The only `worker_threads` use in the backend is
  RAW decoding. That claim is what made worker threads look like a restoration
  of intended behaviour rather than the new architecture it would be.

## Decision

Job handlers continue to run on the main event loop, in one process, one at a
time. The three synchronous handlers yield cooperatively so the HTTP server can
make progress.

1. **Yield with `setImmediate`, behind a named helper.** `setImmediate` runs in
   the check phase, immediately after the poll phase where I/O callbacks fire.
   A microtask yield (`await Promise.resolve()`, `await null`) must **not** be
   used: Node drains the entire microtask queue before returning to the loop's
   phases, so it would look like a fix, pass review, and change nothing.
2. **Budget the yield by elapsed time, not iteration count.** Yield when more
   than ~50ms has passed since the last one. Per-iteration cost varies by an
   order of magnitude — a KNN over a dense neighbourhood against a sparse one —
   so a fixed `every N iterations` gives an unpredictable worst case, while
   yielding every iteration spends ~43k event-loop turns to no benefit.
3. **Fuse the yield to the cancel check.** Every blocking loop already opens by
   polling `runner.isCancelled(jobId)`. One combined asynchronous call performs
   both, so a correctly-written cancel check cannot omit the yield.
   `catalog_sync`'s `isCancelled` callback widens to the asynchronous form so all
   three handlers are fixed the same way.
4. **Never yield inside an open transaction.** `libraryWrite` is
   `BEGIN IMMEDIATE`/`COMMIT`; yielding under it would hold the write lock across
   the yield, and its `SQLITE_BUSY` backoff spins in a synchronous
   `Atomics.wait` — so a contending writer would block the very loop the yield
   was meant to free. The helper throws when the library connection reports
   `inTransaction`, in production as well as development.

The bar is that `/api/status` and `/api/jobs/*` answer within roughly one second
while any job runs.

## Consequences

- **One job at a time is now a load-bearing invariant, not an accident.** The
  processor serializes handlers, and several of them clear and rebuild whole
  tables — `batch_catalog_similarity` wipes all similarity results before it
  starts. Concurrent jobs would corrupt each other's output. Any future
  parallelism work must address that first.
- **Job startup still stalls, deliberately.** Synchronous setup phases outside
  the loops are not covered: `buildBurstSegments` parses and sorts ~43k rows in
  one pass, and describe/score/embed each build a ~43k-key `Set` to pre-filter.
  These are one-off stalls of a few seconds at job start. Accepted as a known
  limit; a few seconds and forty minutes are different user experiences.
- **No standing regression guard.** An event-loop lag watchdog reporting into job
  logs, and a permanent responsiveness test, were both considered and declined as
  surface area not worth carrying. A handler added later can reintroduce the
  stall, and review is the only thing that will catch it. The fused
  yield-and-cancel call is the sole structural mitigation.
- **The three handlers' pass functions become asynchronous.** Their callers
  already were, so the ripple is contained.
- This does nothing for throughput. Jobs take exactly as long as before, plus
  negligible yield overhead.

## Alternatives considered

- **Move handlers onto `worker_threads`** — rejected. It is structurally immune
  to this bug class, which is a genuine advantage, but the goal here is latency
  and not parallelism, and one-job-at-a-time forecloses the parallelism a worker
  pool would buy. The costs are concrete: socket.io is bound to the main-thread
  HTTP server, so every progress emit needs a `postMessage` bridge back; the
  runner needs a per-worker `visualizer.db` handle; and nine test files drive
  `tick()` synchronously and would need a worker harness. Reconsider this if the
  goal ever becomes throughput — the `library.db` access pattern is already
  worker-friendly, since `withLibraryDb` opens and closes per handler scope.
- **Run jobs in a separate process** — rejected for the same reasons as worker
  threads, plus IPC and process lifecycle management.
- **A fixed `every N iterations` yield** — rejected; see Decision (2).
- **Accept the stall and fix only the frontend** — rejected, though the frontend
  half was split out and fixed independently
  ([#314](https://github.com/ccanalesb/lightroom-tagger/issues/314)). Honest
  degradation is worth having on its own, but it does not make a job cancellable.
- **Chunk the synchronous setup phases too** — rejected for now; fiddly work for
  a stall users are unlikely to distinguish from normal startup.
