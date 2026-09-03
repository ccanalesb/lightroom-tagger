/**
 * Pluggable error escalation policies for the fallback dispatcher.
 * Port of `core/error_policy.py`.
 *
 * Two separate concerns live here. `ConsecutiveAbortTracker` is a *session*
 * counter — it exists so a batch of 40,000 images stops after three consecutive
 * rate limits instead of grinding through the whole queue collecting 429s. The
 * policies are *per-call*: they mutate the call state and ask for a retry, which
 * is how the max_tokens ladder and the 413 payload split work.
 */
import { ContextLengthError, InvalidRequestError, PayloadTooLargeError, RateLimitError } from './errors.js';

export const MAX_TOKENS_ESCALATION = [256, 4096, 32768, 65536];
export const BATCH_MAX_TOKENS_ESCALATION = [4096, 32768, 65536];

export const RATE_LIMIT_ABORT_THRESHOLD = 3;
export const FATAL_ABORT_THRESHOLD = 3;

/**
 * Session-level consecutive rate-limit and fatal counters.
 *
 * Owned by the dispatcher and consulted before each dispatch. The scoring loop
 * reads `fatalAbortReached` to stop orchestrating candidates rather than
 * re-inspecting the error types itself.
 */
export class ConsecutiveAbortTracker {
  private readonly rateLimitThreshold: number;
  private readonly fatalThreshold: number;
  private rateLimits = 0;
  private fatal = 0;

  constructor(
    opts: { rateLimitThreshold?: number; fatalThreshold?: number } = {},
  ) {
    this.rateLimitThreshold = opts.rateLimitThreshold ?? RATE_LIMIT_ABORT_THRESHOLD;
    this.fatalThreshold = opts.fatalThreshold ?? FATAL_ABORT_THRESHOLD;
  }

  get consecutiveRateLimits(): number {
    return this.rateLimits;
  }

  get consecutiveFatal(): number {
    return this.fatal;
  }

  get rateLimitAbortReached(): boolean {
    return this.rateLimits >= this.rateLimitThreshold;
  }

  get fatalAbortReached(): boolean {
    return this.fatal >= this.fatalThreshold;
  }

  /** A success clears the rate-limit streak but deliberately not the fatal one. */
  recordSuccess(): void {
    this.rateLimits = 0;
  }

  recordRateLimit(): void {
    this.rateLimits += 1;
    this.fatal = 0;
  }

  recordFatal(): void {
    this.rateLimits = 0;
    this.fatal += 1;
  }

  recordTransientError(): void {
    this.rateLimits = 0;
    this.fatal = 0;
  }

  /** Update the counters once a dispatch has settled, successfully or not. */
  recordDispatchOutcome(e: unknown): void {
    if (e === null || e === undefined) this.recordSuccess();
    else if (e instanceof RateLimitError) this.recordRateLimit();
    else if (e instanceof InvalidRequestError) this.recordFatal();
    else this.recordTransientError();
  }
}

/** What to do after an escalation-class error. */
export type EscalationAction = 'retry' | 'give_up' | 'split';

/** Mutable per-call state a policy may modify before asking for a retry. */
export type CallState = Record<string, unknown>;

export interface ErrorPolicy {
  onEscalationError(
    e: unknown,
    ctx: { providerId: string; model: string; operation: string; callState: CallState },
  ): EscalationAction;
}

/** No mutation — the plain retry and fallback behaviour. */
export class NoOpErrorPolicy implements ErrorPolicy {
  onEscalationError(): EscalationAction {
    return 'retry';
  }
}

/**
 * Climb a `max_tokens` ladder on a context-length error, then blacklist.
 *
 * The per-session cache matters on a batch: once a model is known to need 4096
 * tokens, every later image starts there instead of failing at 256 first. And a
 * model that fails at the top of the ladder is blacklisted for the session, so
 * the batch stops paying for a call that cannot succeed.
 */
export class ContextLengthEscalationPolicy implements ErrorPolicy {
  private readonly ladderValues: number[];
  private readonly modelMinTokens = new Map<string, number>();
  private readonly brokenProviderModels = new Set<string>();

  constructor(ladder?: readonly number[]) {
    this.ladderValues = [...(ladder ?? MAX_TOKENS_ESCALATION)];
  }

  get ladder(): number[] {
    return [...this.ladderValues];
  }

  get minTokens(): Map<string, number> {
    return new Map(this.modelMinTokens);
  }

  get broken(): Set<string> {
    return new Set(this.brokenProviderModels);
  }

  providerKey(providerId: string, model: string): string {
    return `${providerId}:${model}`;
  }

  isBroken(providerId: string, model: string): boolean {
    return this.brokenProviderModels.has(this.providerKey(providerId, model));
  }

  /** The ladder index to start at, given what this model has needed before. */
  startingIndex(providerId: string, model: string): number {
    const cachedMin = this.modelMinTokens.get(this.providerKey(providerId, model)) ?? 0;
    const index = this.ladderValues.findIndex((val) => val >= cachedMin);
    return index === -1 ? 0 : index;
  }

  maxTokensAt(index: number): number {
    return this.ladderValues[index]!;
  }

  onEscalationError(
    e: unknown,
    ctx: { providerId: string; model: string; operation: string; callState: CallState },
  ): EscalationAction {
    if (!(e instanceof ContextLengthError)) return 'retry';

    const key = this.providerKey(ctx.providerId, ctx.model);
    const idx = Math.trunc(Number(ctx.callState.token_index ?? 0));

    if (idx < this.ladderValues.length - 1) {
      const newIdx = idx + 1;
      const nextVal = this.ladderValues[newIdx]!;
      this.modelMinTokens.set(key, nextVal);
      ctx.callState.token_index = newIdx;
      ctx.callState._log_message =
        `[${ctx.operation}] Escalating max_tokens to ${nextVal} for ${ctx.model}`;
      return 'retry';
    }

    this.brokenProviderModels.add(key);
    ctx.callState._log_message =
      `[${ctx.operation}] max_tokens exhausted at ${this.ladderValues[idx]} ` +
      `for ${ctx.model}, blacklisting for session`;
    return 'give_up';
  }
}

/** Batch vision: the context-length ladder plus a payload split on 413. */
export class VisionBatchErrorPolicy implements ErrorPolicy {
  private readonly tokenPolicy: ContextLengthEscalationPolicy;

  constructor(opts: { tokenLadder?: readonly number[]; tokenPolicy?: ContextLengthEscalationPolicy } = {}) {
    this.tokenPolicy =
      opts.tokenPolicy ??
      new ContextLengthEscalationPolicy(opts.tokenLadder ?? BATCH_MAX_TOKENS_ESCALATION);
  }

  get ladder(): number[] {
    return this.tokenPolicy.ladder;
  }

  get minTokens(): Map<string, number> {
    return this.tokenPolicy.minTokens;
  }

  get broken(): Set<string> {
    return this.tokenPolicy.broken;
  }

  providerKey(providerId: string, model: string): string {
    return this.tokenPolicy.providerKey(providerId, model);
  }

  isBroken(providerId: string, model: string): boolean {
    return this.tokenPolicy.isBroken(providerId, model);
  }

  startingIndex(providerId: string, model: string): number {
    return this.tokenPolicy.startingIndex(providerId, model);
  }

  maxTokensAt(index: number): number {
    return this.tokenPolicy.maxTokensAt(index);
  }

  onEscalationError(
    e: unknown,
    ctx: { providerId: string; model: string; operation: string; callState: CallState },
  ): EscalationAction {
    if (e instanceof PayloadTooLargeError) {
      const candidates = (ctx.callState.candidates as unknown[] | undefined) ?? [];
      // A single item that is still too large cannot be split further.
      if (candidates.length <= 1) {
        ctx.callState._log_message =
          `[${ctx.operation}] single-item chunk still too large, skipping`;
        return 'give_up';
      }
      const half = Math.floor(candidates.length / 2);
      ctx.callState._split_halves = [candidates.slice(0, half), candidates.slice(half)];
      ctx.callState._log_message =
        `[${ctx.operation}] payload too large, splitting ` +
        `${candidates.length} -> ${half}+${candidates.length - half}`;
      return 'split';
    }
    return this.tokenPolicy.onEscalationError(e, ctx);
  }
}
