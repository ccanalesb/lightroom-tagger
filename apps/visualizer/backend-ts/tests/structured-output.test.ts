/**
 * Score payload validation and repair.
 *
 * Mirrors `lightroom_tagger/core/test_structured_output.py` case for case, since
 * the two implementations have to agree on which malformed answers are salvaged
 * and which are rejected — a payload Python accepted and this rejects would show
 * up as a catalog that stops scoring after cutover.
 */
import { describe, expect, it, vi } from 'vitest';
import {
  parseScoreResponse,
  parseScoreResponseWithRetry,
  repairJsonText,
  ScoreResponse,
  STRUCTURED_OUTPUT_MAX_CHARS,
  STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS,
  StructuredOutputError,
} from '../src/vision/structured-output.js';

const RAW_TRAILING_COMMA = '{"perspective_slug":"street","score":6,"rationale":"ok",}';
const RAW_FENCE = '```json\n{"perspective_slug":"doc","score":8,"rationale":"inside fence"}\n```';
const RAW_INVALID_TYPE = 'totally not json {{{';
const RAW_LLM_FIXER_SAVES = '%%%garbage%%%';
const RAW_PREVIEW_TRUNCATION = 'Z'.repeat(400) + '{{not_valid';

const valid = (slug: string, score: number) =>
  JSON.stringify({ perspective_slug: slug, score, rationale: 'fixed' });

describe('deterministic repair', () => {
  it('drops a trailing comma before the closing brace', () => {
    const m = parseScoreResponse(RAW_TRAILING_COMMA);
    expect(m).toMatchObject({ perspective_slug: 'street', score: 6, rationale: 'ok' });
  });

  it('unwraps a markdown fence', () => {
    const m = parseScoreResponse(RAW_FENCE);
    expect(m).toMatchObject({ perspective_slug: 'doc', score: 8 });
  });

  /** One pass leaves `,,]` half-cleaned, so the sweep runs to a fixed point. */
  it('removes stacked trailing commas', () => {
    expect(repairJsonText('{"a":[1,2,,],}')).toBe('{"a":[1,2]}');
  });
});

describe('validation', () => {
  it('rejects a score above ten', () => {
    expect(ScoreResponse.safeParse({ perspective_slug: 'a', score: 11, rationale: 'b' }).success)
      .toBe(false);
  });

  it('rejects an unknown key rather than silently dropping it', () => {
    const parsed = ScoreResponse.safeParse({
      perspective_slug: 'a',
      score: 5,
      rationale: 'b',
      confidence: 0.9,
    });
    expect(parsed.success).toBe(false);
  });

  it('defaults not_attempted to false when absent', () => {
    expect(parseScoreResponse(valid('street', 6)).not_attempted).toBe(false);
  });

  it('parses an explicit not_attempted', () => {
    const m = parseScoreResponse(
      '{"perspective_slug":"street","score":5,"rationale":"absent","not_attempted":true}',
    );
    expect(m).toMatchObject({ not_attempted: true, score: 5 });
  });
});

describe('parseScoreResponseWithRetry', () => {
  it('reports unparseable output as a validation failure', async () => {
    await expect(parseScoreResponseWithRetry(RAW_INVALID_TYPE)).rejects.toThrow(
      'Score response validation failed',
    );
  });

  it('accepts a repair from the LLM fixer and flags it', async () => {
    const { parsed, repaired } = await parseScoreResponseWithRetry(RAW_LLM_FIXER_SAVES, {
      llmFixer: () => valid('street', 7),
    });
    expect(repaired).toBe(true);
    expect(parsed).toMatchObject({ perspective_slug: 'street', score: 7 });
  });

  it('logs the repair under the prefix the log filters match on', async () => {
    const logRepair = vi.fn();
    await parseScoreResponseWithRetry(RAW_LLM_FIXER_SAVES, {
      llmFixer: () => valid('publisher', 5),
      logRepair,
    });
    expect(logRepair).toHaveBeenCalledOnce();
    expect(logRepair.mock.calls[0]![0]).toMatch(/^\[structured_output\] repaired:/);
  });

  it('calls the fixer once and then gives up', async () => {
    const llmFixer = vi.fn(() => 'still not json');
    await expect(
      parseScoreResponseWithRetry(RAW_LLM_FIXER_SAVES, { llmFixer }),
    ).rejects.toThrow(StructuredOutputError);
    expect(llmFixer).toHaveBeenCalledOnce();
  });

  it('does not repair a payload that was already valid', async () => {
    const llmFixer = vi.fn(() => valid('street', 1));
    const { repaired } = await parseScoreResponseWithRetry(valid('street', 4), { llmFixer });
    expect(repaired).toBe(false);
    expect(llmFixer).not.toHaveBeenCalled();
  });

  /**
   * A provider that is unreachable is a different failure from a repair that came
   * back still-broken, and must not be reported as bad JSON.
   */
  it('propagates an error thrown by the fixer itself', async () => {
    await expect(
      parseScoreResponseWithRetry(RAW_LLM_FIXER_SAVES, {
        llmFixer: () => {
          throw new Error('connection refused');
        },
      }),
    ).rejects.toThrow('connection refused');
  });

  it('bounds the raw preview it carries into the error', async () => {
    await expect(parseScoreResponseWithRetry(RAW_PREVIEW_TRUNCATION)).rejects.toSatisfy(
      (e: unknown) => {
        const preview = (e as StructuredOutputError).rawPreview;
        return preview !== null && preview.length <= STRUCTURED_OUTPUT_RAW_PREVIEW_MAX_CHARS;
      },
    );
  });

  /**
   * The size gate fires before anything else, so a runaway response never becomes
   * a second provider call carrying half a megabyte of garbage.
   */
  it('rejects an oversized payload without calling the fixer', async () => {
    const llmFixer = vi.fn(() => valid('street', 3));
    const huge = 'x'.repeat(STRUCTURED_OUTPUT_MAX_CHARS + 1);

    await expect(parseScoreResponseWithRetry(huge, { llmFixer })).rejects.toThrow(
      'input too large',
    );
    expect(llmFixer).not.toHaveBeenCalled();
  });
});

describe('StructuredOutputError.describe', () => {
  it('joins the message, the validation errors and the preview', () => {
    const err = new StructuredOutputError('Score response validation failed', {
      rawPreview: 'raw text',
      validationErrors: ['score: too big', 'rationale: required'],
    });
    expect(err.describe()).toBe(
      'Score response validation failed Errors: score: too big; rationale: required ' +
        'Raw preview: raw text',
    );
  });

  it('carries the failing field so the log names it', async () => {
    let err: StructuredOutputError | undefined;
    try {
      await parseScoreResponseWithRetry('{"perspective_slug":"street","score":42,"rationale":"ok"}');
    } catch (e) {
      err = e as StructuredOutputError;
    }
    expect(err?.validationErrors.join(' ')).toContain('score:');
  });
});
