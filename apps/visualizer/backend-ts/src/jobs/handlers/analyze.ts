/**
 * The unified analyze job. Port of `handle_batch_analyze` in
 * `jobs/handlers/analyze.py`.
 *
 * Describe then score, over **one** selection. That sharing is the whole point:
 * running the two batch jobs back to back selects twice, and between the two
 * selections the second one has changed — every image the first job just
 * described is now described, so a scoring selection derived from "undescribed"
 * would be empty. Here the images are chosen once and both passes see the same
 * list, which is also what lets the job report a single pair of totals.
 *
 * Everything that makes a pass behave as a stage rather than as its own job — the
 * progress band, the log prefix, the checkpoint slot, who calls `completeJob` —
 * is carried by the `PassStage` argument the passes take.
 */
import type { Db } from '../../db/connection.js';
import { fingerprintBatchDescribe, readAnalyzeCheckpoint } from '../checkpoint.js';
import type { JobRunner } from '../runner.js';
import {
  asMetadata,
  failureSeverityFromError,
  filterVoidSubstanceFromScoringSelection,
  resolveLibraryDbOrFail,
  withLibraryDb,
  type PassStage,
} from './common.js';
import { runDescribePass, selectDescribeCandidates } from './describe.js';
import { mergeSkipReasonCounts } from './path-diagnostics.js';
import { runScorePass } from './score.js';

/**
 * Describe gets the first half of the bar and scoring the second, with the four
 * points between them reserved for frame-substance detection — the stage Python
 * runs there, which lands with the detector port. Leaving the gap rather than
 * closing it keeps the two bands where a resumed Flask-era job expects them.
 */
const DESCRIBE_STAGE: PassStage = {
  progressRange: [0, 48],
  logPrefix: '[describe] ',
  checkpointKey: 'describe',
};

const SCORE_STAGE: PassStage = {
  progressRange: [52, 100],
  logPrefix: '[score] ',
  checkpointKey: 'score',
};

/** What the composite needs from a stage, under names that fit both passes. */
interface StageOutcome {
  total: number;
  succeeded: number;
  failed: number;
  skipReasonCounts: unknown;
}

export interface BatchAnalyzeResult {
  describe_total: number;
  describe_succeeded: number;
  describe_failed: number;
  score_total: number;
  score_succeeded: number;
  score_failed: number;
  skip_reason_counts: Record<string, number>;
}

/** Describe then score every catalog image in the window, as one job. */
export async function handleBatchAnalyze(
  runner: JobRunner,
  jobId: string,
  rawMetadata: unknown,
): Promise<void> {
  const metadata = asMetadata(rawMetadata);
  try {
    const dbPath = resolveLibraryDbOrFail(runner, jobId);
    if (dbPath === null) return;

    await withLibraryDb(dbPath, async (db) => {
      const imageType = String(metadata['image_type'] ?? 'catalog');
      if (imageType !== 'catalog') {
        runner.failJob(jobId, 'image_type must be catalog');
        return;
      }

      // The two passes disagree about what `force` means, so each gets its own
      // view of the metadata. This is also what the sub-fingerprints hash, which
      // is why the split happens before selection rather than inside the passes.
      const describeMetadata = { ...metadata, force: Boolean(metadata['force_describe']) };
      const scoreMetadata = { ...metadata, force: Boolean(metadata['force_score']) };

      const selection = selectDescribeCandidates(
        runner,
        jobId,
        db,
        metadata,
        Boolean(metadata['force_describe']),
      );

      const describe = await runDescribeStage(runner, jobId, describeMetadata, db, selection);
      if (describe === null) return;

      // Condemned frames were still worth describing — a lens cap has a filename
      // and a date — but scoring one produces a rating of nothing.
      const scoreSelection = filterVoidSubstanceFromScoringSelection(db, selection);

      runner.setCurrentStep(jobId, 'Scoring');
      const scoreSummary = await runScorePass(
        runner,
        jobId,
        scoreMetadata,
        db,
        scoreSelection,
        SCORE_STAGE,
      );
      if (scoreSummary === null) return;

      const result: BatchAnalyzeResult = {
        describe_total: describe.total,
        describe_succeeded: describe.succeeded,
        describe_failed: describe.failed,
        score_total: scoreSummary.total,
        score_succeeded: scoreSummary.scored,
        score_failed: scoreSummary.failed,
        skip_reason_counts: mergeSkipReasonCounts(
          describe.skipReasonCounts,
          scoreSummary.skip_reason_counts,
        ),
      };
      runner.clearCheckpoint(jobId);
      runner.completeJob(jobId, result);
    });
  } catch (e) {
    runner.failJob(jobId, e instanceof Error ? e.message : String(e), failureSeverityFromError(e));
  }
}

/**
 * Run the describe stage, or recognize that a previous run already finished it.
 *
 * A job interrupted while scoring resumes with `stage: 'score'` in its
 * checkpoint. Re-entering the describe pass would be nearly free — every pair is
 * in the processed set — but only *nearly*: it would re-run the preflight and the
 * pre-filter over the whole selection to arrive at zero work. The fingerprint
 * check is what makes skipping it safe, since a moved selection is a different
 * describe run and has to start over.
 *
 * Returns `null` when the stage settled the job.
 */
async function runDescribeStage(
  runner: JobRunner,
  jobId: string,
  describeMetadata: Record<string, unknown>,
  db: Db,
  selection: readonly (readonly [string, string])[],
): Promise<StageOutcome | null> {
  const fingerprint = await fingerprintBatchDescribe(describeMetadata, selection);
  const checkpoint = readAnalyzeCheckpoint(runner.readMetadata(jobId));

  if (checkpoint.stage === 'score' && checkpoint.describe['fingerprint'] === fingerprint) {
    const total = Number(checkpoint.describe['total_at_start'] ?? 0);
    // Zero succeeded because this run described nothing; the count that mattered
    // belonged to the run that was interrupted and is not recoverable from the
    // checkpoint, which stores what is done, not how it went.
    return {
      total: Number.isFinite(total) ? Math.trunc(total) : 0,
      succeeded: 0,
      failed: 0,
      skipReasonCounts: null,
    };
  }

  runner.setCurrentStep(jobId, 'Describing');
  const summary = await runDescribePass(
    runner,
    jobId,
    describeMetadata,
    db,
    selection,
    DESCRIBE_STAGE,
  );
  if (summary === null) return null;
  return {
    total: summary.total,
    succeeded: summary.described,
    failed: summary.failed,
    skipReasonCounts: summary.skip_reason_counts,
  };
}
