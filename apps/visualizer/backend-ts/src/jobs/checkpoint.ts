/**
 * Resume checkpoints, stored in `jobs.metadata.checkpoint`.
 * Port of `jobs/checkpoint.py`.
 *
 * A batch job describes tens of thousands of images through a paid API, so a
 * restart must not re-run the work already paid for. The checkpoint records which
 * units are done, and a fingerprint of the inputs that produced them — resuming
 * against a *different* selection would silently skip images the user just asked
 * for, so a fingerprint mismatch discards the checkpoint and says so in the log.
 *
 * `batch_describe` — `job_type`, `fingerprint`, `processed_pairs` (`"key|itype"`),
 * `total_at_start`.
 *
 * `batch_embed_image` — the same shape, except `processed_pairs` holds bare
 * catalog keys. The key name is not a mistake to tidy up: it is what the Flask
 * backend already wrote, and renaming it here would strand every checkpoint the
 * cutover is meant to resume.
 *
 * `batch_stack_detect` — bare catalog keys again, but under
 * `processed_image_keys`. Same reason: the name is the Flask backend's.
 */
import { CLIP_EMBED_DIM, CLIP_EMBED_MODEL_ID } from '../imaging/clip-embed.js';

export const CHECKPOINT_VERSION = 1;

/** Refuse to grow a checkpoint past this; `jobs.metadata` is one JSON column. */
export const CHECKPOINT_MAX_ENTRIES = 100_000;

/**
 * `json.dumps(payload, sort_keys=True, separators=(",", ":"))`, byte for byte.
 *
 * The fingerprint has to survive the cutover: a job checkpointed by the Flask
 * backend must resume under this one rather than restarting from zero, and that
 * only holds if both sides hash the same bytes. Python sorts object keys and
 * escapes non-ASCII, neither of which `JSON.stringify` does.
 */
export function canonicalJson(value: unknown): string {
  return escapeNonAscii(JSON.stringify(sortKeys(value)));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value === null || typeof value !== 'object') return value;
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(value as Record<string, unknown>).sort()) {
    out[key] = sortKeys((value as Record<string, unknown>)[key]);
  }
  return out;
}

function escapeNonAscii(json: string): string {
  // Only string contents can hold non-ASCII, and `JSON.stringify` has already
  // escaped everything else, so a blind pass over the output is safe. Lone
  // surrogates escape individually, which is what Python emits too.
  return json.replace(/[\u0080-\uffff]/g, (c) =>
    `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`,
  );
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Coerce a metadata value to an int, or `null` when it is not one. */
function asIntOrNull(raw: unknown): number | null {
  if (raw === null || raw === undefined) return null;
  const n = typeof raw === 'number' ? raw : Number(raw);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

/** Sorted `perspective_slugs`, or `null` when the list is absent or empty. */
function perspectiveSlugsFingerprint(metadata: Record<string, unknown>): string[] | null {
  const raw = metadata['perspective_slugs'];
  if (!Array.isArray(raw) || raw.length === 0) return null;
  return raw.map((x) => String(x)).sort();
}

/** Identity of a `batch_describe` run: its knobs plus the ordered work list. */
export function fingerprintBatchDescribe(
  metadata: Record<string, unknown>,
  orderedPairs: readonly (readonly [string, string])[],
): Promise<string> {
  return sha256Hex(
    canonicalJson({
      backfill_visual_tags: Boolean(metadata['backfill_visual_tags']),
      date_filter: metadata['date_filter'] ?? 'all',
      force: Boolean(metadata['force']),
      image_type: metadata['image_type'] ?? 'catalog',
      max_workers: asIntOrNull(metadata['max_workers'] ?? 4) ?? 4,
      min_rating: asIntOrNull(metadata['min_rating']),
      pairs: orderedPairs.map(([key, itype]) => `${key}|${itype}`),
      perspective_slugs: perspectiveSlugsFingerprint(metadata),
      provider_id: metadata['provider_id'] ?? null,
      provider_model: metadata['provider_model'] ?? null,
    }),
  );
}

/**
 * Identity of a `batch_embed_image` run.
 *
 * The date window arrives already resolved rather than being re-read from the
 * metadata, because the same window has several spellings — `date_filter:
 * '3months'` and `last_months: 3` mean one thing — and fingerprinting the raw
 * text would discard a checkpoint over a change of wording.
 *
 * The model id and dimension are in the payload because a re-embed under a
 * different model is a different run: resuming across that would leave the table
 * holding two incompatible vector spaces.
 */
export function fingerprintBatchEmbedImage(
  metadata: Record<string, unknown>,
  orderedKeys: readonly string[],
  window: { resolvedMonths: number | null; resolvedYear: string | null },
): Promise<string> {
  return sha256Hex(
    canonicalJson({
      embedding_dim: CLIP_EMBED_DIM,
      embedding_model_id: CLIP_EMBED_MODEL_ID,
      force: Boolean(metadata['force']),
      image_type: 'catalog',
      min_rating: asIntOrNull(metadata['min_rating']),
      pairs: [...orderedKeys].sort(),
      resolved_months: window.resolvedMonths,
      resolved_year: window.resolvedYear,
    }),
  );
}

/**
 * Identity of a `batch_stack_detect` run: the work list, the burst gap, and the
 * force mode.
 *
 * The gap and the mode arrive resolved, not read from the metadata, because both
 * have a default the metadata does not spell — `delta_ms` falls back to
 * `config.yaml` and an absent `force` means `incremental`. A run resumed after the
 * config changed is a different grouping of the same photos, so it must not match.
 */
export function fingerprintBatchStackDetect(
  imageKeys: readonly string[],
  opts: { resolvedDeltaMs: number; forceMode: string },
): Promise<string> {
  return sha256Hex(
    canonicalJson({
      delta_ms: Math.trunc(opts.resolvedDeltaMs),
      force_mode: String(opts.forceMode),
      keys: [...imageKeys].sort(),
    }),
  );
}

export function buildBatchDescribeCheckpointBody(args: {
  fingerprint: string;
  processed: ReadonlySet<string>;
  totalAtStart: number;
}): Record<string, unknown> {
  return {
    job_type: 'batch_describe',
    fingerprint: args.fingerprint,
    processed_pairs: [...args.processed].sort(),
    total_at_start: args.totalAtStart,
  };
}

export function buildBatchEmbedImageCheckpointBody(args: {
  fingerprint: string;
  processed: ReadonlySet<string>;
  totalAtStart: number;
}): Record<string, unknown> {
  return {
    job_type: 'batch_embed_image',
    fingerprint: args.fingerprint,
    processed_pairs: [...args.processed].sort(),
    total_at_start: args.totalAtStart,
  };
}

export function buildBatchStackDetectCheckpointBody(args: {
  fingerprint: string;
  processed: ReadonlySet<string>;
  totalAtStart: number;
}): Record<string, unknown> {
  return {
    job_type: 'batch_stack_detect',
    fingerprint: args.fingerprint,
    processed_image_keys: [...args.processed].sort(),
    total_at_start: args.totalAtStart,
  };
}

export interface LoadResumeStateArgs {
  metadata: Record<string, unknown>;
  jobType: string;
  /** Which array in the checkpoint body holds the processed units. */
  resumeKey: 'processed_pairs' | 'processed_triplets' | 'processed_image_keys';
  fingerprint: string;
  /** Logged when a checkpoint exists but was built from different inputs. */
  mismatchMessage: string | null;
  log: (message: string) => void;
}

/**
 * The processed-unit set to resume from, or an empty set.
 *
 * Silent on a missing or stale-version checkpoint — there is nothing to tell the
 * user. Loud on a fingerprint mismatch, because that one means work they expected
 * to be skipped is about to be redone.
 */
export function loadResumeState(args: LoadResumeStateArgs): Set<string> {
  const chk = args.metadata['checkpoint'];
  if (!chk || typeof chk !== 'object' || Array.isArray(chk)) return new Set();
  const body = chk as Record<string, unknown>;
  if (body['checkpoint_version'] !== CHECKPOINT_VERSION) return new Set();
  if (body['job_type'] !== args.jobType) return new Set();

  if (body['fingerprint'] === args.fingerprint) {
    const units = body[args.resumeKey];
    return new Set(Array.isArray(units) ? units.map((u) => String(u)) : []);
  }
  if (body['fingerprint'] && args.mismatchMessage) args.log(args.mismatchMessage);
  return new Set();
}
