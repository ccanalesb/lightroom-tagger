/**
 * The `catalog_sync` job handler. Port of `jobs/handlers/catalog.py`.
 *
 * The handler is thin because the work is in `lightroom/catalog-sync.ts`; what it
 * owns is the two ways the job can be unrunnable — no catalog configured, or the
 * configured one is not there — and both are the user's own configuration, so they
 * fail as `warning` rather than as a defect.
 *
 * Python's `_handle_catalog_sync_inner` also carries a `chain_mode` branch for
 * `catalog_cache_build`, which turns those failures into a logged stage result and
 * suppresses progress. That branch is not here for the reason the embed and stacks
 * handlers do not have one either: `catalog_cache_build` is the only caller, and the
 * suppression is easier to get right beside the composite than guessed at from here.
 */
import { existsSync } from 'node:fs';
import { config, loadLibraryConfig } from '../../config.js';
import {
  CATALOG_LOCKED_MSG,
  CatalogSyncError,
  syncCatalog,
  type SyncCatalogOutcome,
} from '../../lightroom/catalog-sync.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  jobLogLevel,
  resolveLibraryDbOrFail,
  withLibraryDb,
} from './common.js';

/** `catalog_path` from the job's metadata, else from `config.yaml`. */
function resolveCatalogPath(metadata: Record<string, unknown>): string | null {
  const fromMetadata = metadata['catalog_path'];
  if (fromMetadata) return String(fromMetadata);
  return loadLibraryConfig(config.LT_CONFIG_YAML).catalogPath;
}

/** Refresh `library.db` from the Lightroom catalog, additions only. */
export async function handleCatalogSync(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  const dbPath = resolveLibraryDbOrFail(runner, jobId);
  if (dbPath === null) return;

  const catalogPath = resolveCatalogPath(metadata);
  if (!catalogPath) {
    runner.failJob(
      jobId,
      'No catalog path configured. Set catalog_path in config.yaml.',
      'warning',
    );
    return;
  }
  if (!existsSync(catalogPath)) {
    runner.failJob(jobId, `Catalog not found: ${catalogPath}`, 'warning');
    return;
  }

  runner.updateProgress(jobId, 5, 'Connecting to Lightroom catalog...');

  await withLibraryDb(dbPath, async (libDb) => {
    let outcome: SyncCatalogOutcome;
    try {
      outcome = syncCatalog(catalogPath, libDb, {
        log: (level, message) => runner.log(jobId, jobLogLevel(level), message),
        progress: (pct, message) => runner.updateProgress(jobId, pct, message),
        isCancelled: () => runner.isCancelled(jobId),
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      if (e instanceof CatalogSyncError) {
        // Its message is the whole value of this error type, so an empty one is
        // worth replacing with the reason it almost always has.
        runner.failJob(jobId, message || CATALOG_LOCKED_MSG, 'warning');
      } else {
        runner.failJob(jobId, message, failureSeverityFromError(e));
      }
      return;
    }

    if (outcome.cancelled) {
      runner.finalizeCancelled(jobId);
      return;
    }
    runner.completeJob(jobId, outcome.result);
  });
}
