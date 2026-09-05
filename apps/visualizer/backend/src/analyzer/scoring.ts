/**
 * The per-perspective scoring vision operation.
 *
 * Same image preparation and cleanup as `buildDescriptionOpSpec`. The parser
 * validates score output and allows one LLM JSON repair attempt.
 */
import { unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { compressImage, getViewablePathManaged } from '../imaging/image-prep.js';
import { ProviderRegistry } from '../providers/registry.js';
import type { CancelCheck, LogCallback } from '../providers/retry.js';
import { generateDescription, makeScoreJsonLlmFixer } from '../providers/vision-client.js';
import {
  parseScoreResponseWithRetry,
  type ScoreResponse,
} from '../vision/structured-output.js';
import type { VisionOpSpec } from '../vision/vision-op.js';

/** A validated score, plus whether it survived only because repair rescued it. */
export interface ParsedScore {
  parsed: ScoreResponse;
  repaired: boolean;
}

/** Validate score output, with one LLM JSON repair attempt against the same model. */
export async function parseScoreVisionResponse(
  raw: string,
  provider: string,
  model: string,
  opts: { registry?: ProviderRegistry | null; logCallback?: LogCallback } = {},
): Promise<ParsedScore> {
  const registry = opts.registry ?? new ProviderRegistry();
  const client = registry.getClient(provider);

  return parseScoreResponseWithRetry(raw, {
    llmFixer: makeScoreJsonLlmFixer(client, model),
    logRepair: (message) => opts.logCallback?.('info', message),
  });
}

export interface ScoreOpOptions {
  userPrompt: string;
  providerId?: string | null;
  model?: string | null;
  logCallback?: LogCallback;
  /** The path is an already-compressed cache file; do not recompress it. */
  silentCompression?: boolean;
  registry?: ProviderRegistry | null;
  think?: boolean;
  maxTokens?: number;
  cancelCheck?: CancelCheck;
}

/**
 * Build the spec for the scoring vision op.
 *
 * `resolveKind` is `'description'`, not `'score'`: scoring runs on the same
 * vision model as describe and there is no separate configured default for it.
 */
export function buildScoreOpSpec(path: string, opts: ScoreOpOptions): VisionOpSpec<ParsedScore> {
  const tempFiles: string[] = [];

  return {
    resolveKind: 'description',
    operation: 'score',
    providerId: opts.providerId ?? null,
    model: opts.model ?? null,
    logCallback: opts.logCallback ?? null,
    registry: opts.registry ?? null,
    cancelCheck: opts.cancelCheck ?? null,
    parseResponse: (raw, provider, model) =>
      parseScoreVisionResponse(raw, provider, model, {
        registry: opts.registry ?? null,
        logCallback: opts.logCallback ?? null,
      }),
    fnFactory: async () => {
      const viewable = await getViewablePathManaged(path);
      if (viewable.isTemp) tempFiles.push(viewable.path);

      let compressed = viewable.path;
      if (!opts.silentCompression) {
        compressed = await compressImage(viewable.path);
        if (compressed !== viewable.path) tempFiles.push(compressed);
      }

      return (client, mdl) => async () =>
        generateDescription(client, mdl, compressed, {
          logCallback: opts.logCallback ?? null,
          userPrompt: opts.userPrompt,
          think: opts.think ?? false,
          maxTokens: opts.maxTokens ?? 2048,
          // Unreachable: `buildScoringUserPrompt` never returns empty. Naming the
          // describe prompt here instead would ask the model for the wrong schema.
          fallbackPrompt: opts.userPrompt,
        });
    },
    cleanup: async () => {
      for (const f of tempFiles) {
        if (existsSync(f)) await unlink(f).catch(() => undefined);
      }
    },
  };
}
