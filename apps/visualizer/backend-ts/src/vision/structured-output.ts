/**
 * Validation and deterministic JSON repair for score-shaped model output.
 *
 * Every payload bound for `image_scores` goes through here, because a score row
 * is a number the ranking trusts: a malformed answer that quietly became an empty
 * row would be indistinguishable from a real judgment, and would stop the image
 * ever being rescored.
 *
 * Repair is deterministic first — fences and trailing commas, no model call — and
 * only then, at most once, asks the model to fix its own JSON.
 */
import { z } from 'zod';

export const STRUCTURED_OUTPUT_MAX_CHARS = 512_000;
export const STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS = 200;

const FENCE_PATTERN = /```(?:json)?\s*\n?([\s\S]*?)\n?```/;
const TRAILING_COMMA_PATTERN = /,(\s*[}\]])/g;

/** One perspective's numeric verdict, as it lands in `image_scores`. */
export const ScoreResponse = z
  .object({
    perspective_slug: z.string(),
    score: z.int().min(1).max(10),
    rationale: z.string(),
    not_attempted: z.boolean().default(false),
  })
  .strict();

export type ScoreResponse = z.infer<typeof ScoreResponse>;

function truncatePreview(text: string, maxLen = STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 3) + '...';
}

/** Raised when a payload is unusable — too large, or still invalid after repair. */
export class StructuredOutputError extends Error {
  readonly rawPreview: string | null;
  readonly validationErrors: string[];

  constructor(
    message: string,
    opts: { rawPreview?: string | null; validationErrors?: readonly string[] } = {},
  ) {
    super(message);
    this.name = 'StructuredOutputError';
    this.rawPreview = opts.rawPreview != null ? truncatePreview(opts.rawPreview) : null;
    this.validationErrors = [...(opts.validationErrors ?? [])];
  }

  /**
   * The one-line form the job log and the failure reason both show.
   *
   * Python folds this into `__str__`, so every `str(exc)` carries the preview.
   * Here it is a separate method: `error.message` is read directly in far more
   * places in JS than `str(exc)` is in Python, and widening it would change every
   * one of them.
   */
  describe(): string {
    const parts = [this.message];
    if (this.validationErrors.length > 0) {
      parts.push('Errors: ' + this.validationErrors.join('; '));
    }
    if (this.rawPreview !== null) {
      parts.push(`Raw preview: ${truncatePreview(this.rawPreview)}`);
    }
    return parts.join(' ');
  }
}

/**
 * A payload that did not validate — the signal that repair is worth attempting.
 *
 * Python leans on pydantic's `ValidationError` to mean this and reserves
 * `StructuredOutputError` for terminal failures. The two must stay distinct: the
 * retry path catches one and re-raises the other, so collapsing them would send
 * 512 KB of garbage to the provider for an LLM repair attempt.
 */
export class ScoreValidationError extends Error {
  readonly issues: string[];

  constructor(message: string, issues: readonly string[]) {
    super(message);
    this.name = 'ScoreValidationError';
    this.issues = [...issues];
  }
}

function rejectIfTooLarge(raw: string): void {
  if (raw.length > STRUCTURED_OUTPUT_MAX_CHARS) {
    throw new StructuredOutputError('Score response validation failed: input too large', {
      rawPreview: truncatePreview(raw),
      validationErrors: [],
    });
  }
}

function issueMessages(error: z.ZodError): string[] {
  return error.issues.map((issue) => {
    const loc = issue.path.filter((p) => p !== 'body').join('.');
    return `${loc}: ${issue.message}`;
  });
}

/**
 * Normalize the two ways models break JSON that need no model to fix.
 *
 * The trailing-comma sweep runs to a fixed point because a single pass leaves
 * `,,]` half-cleaned. Its limitation is inherited deliberately: a comma
 * immediately before `}` or `]` *inside a string value* is removed too. That is
 * accepted at this tier — the alternative is a JSON tokenizer, and what this sees
 * are one-line rationales.
 */
export function repairJsonText(raw: string): string {
  rejectIfTooLarge(raw);
  let text = raw.trim();

  const fence = FENCE_PATTERN.exec(text);
  if (fence) text = fence[1]!.trim();

  let prev: string | null = null;
  while (prev !== text) {
    prev = text;
    text = text.replace(TRAILING_COMMA_PATTERN, '$1');
  }
  return text;
}

/** Repair *raw* deterministically, then validate it as a score. */
export function parseScoreResponse(raw: string): ScoreResponse {
  const text = repairJsonText(raw);

  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch (e) {
    // Pydantic reports a JSON syntax failure as a validation error with an empty
    // location, so the repair path sees it exactly as it sees a schema violation.
    const detail = `Invalid JSON: ${e instanceof Error ? e.message : String(e)}`;
    throw new ScoreValidationError(detail, [`: ${detail}`]);
  }

  const result = ScoreResponse.safeParse(json);
  if (!result.success) {
    throw new ScoreValidationError(z.prettifyError(result.error), issueMessages(result.error));
  }
  return result.data;
}

/** Ask the model to repair its own JSON. At most one call, never a loop. */
export type LlmFixer = (raw: string, errorSummary: string) => Promise<string> | string;

/**
 * Validate *raw*, with one optional model-assisted repair attempt.
 *
 * `repaired` is true only when the first parse failed and the fixer rescued it,
 * which is what `image_scores.repaired_from_malformed` records — that column
 * exists so "how often is this model returning junk?" can be answered from the
 * catalog rather than from logs that have already rotated away.
 *
 * Python accepts a second, non-LLM `fixer` hook here as well. Nothing has ever
 * passed one except its own unit test, so it is not ported.
 */
export async function parseScoreResponseWithRetry(
  raw: string,
  opts: { llmFixer?: LlmFixer | null; logRepair?: ((message: string) => void) | null } = {},
): Promise<{ parsed: ScoreResponse; repaired: boolean }> {
  rejectIfTooLarge(raw);

  let first: ScoreValidationError;
  try {
    return { parsed: parseScoreResponse(raw), repaired: false };
  } catch (e) {
    if (!(e instanceof ScoreValidationError)) throw e;
    first = e;
  }

  if (opts.llmFixer) {
    // The fixer call itself is outside the catch: a provider being unreachable is
    // a different failure from the repair coming back still-broken, and reporting
    // it as "validation failed" would send someone reading the rationale text.
    const candidate = await opts.llmFixer(raw, first.message);
    try {
      const parsed = parseScoreResponse(candidate);
      opts.logRepair?.('[structured_output] repaired: LLM JSON repair returned valid score JSON.');
      return { parsed, repaired: true };
    } catch (e) {
      if (!(e instanceof ScoreValidationError) && !(e instanceof StructuredOutputError)) throw e;
    }
  }

  throw new StructuredOutputError('Score response validation failed', {
    rawPreview: raw.length <= STRUCTURED_OUTPUT_MAX_CHARS ? repairJsonText(raw) : raw,
    validationErrors: first.issues,
  });
}
