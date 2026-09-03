/**
 * Configurable retry with exponential backoff for provider calls.
 * Port of `core/retry.py`.
 *
 * The Python version needed `_interruptible_sleep` and a thread-local
 * `cancel_scope`, because `time.sleep(32)` inside a backoff held the worker for
 * the full duration regardless of `runner.is_cancelled` — the exact failure that
 * left job `b141dbcc` CPU-pegged for nine minutes after a cancel. And threading a
 * cancel check through runner → handler → description_service → analyzer →
 * dispatcher → retry was five layers of signature plumbing, hence the
 * thread-local.
 *
 * Neither is needed here. `await sleep()` does not hold anything, so the check
 * before each slice is only about *promptness*, and an explicit optional
 * `cancelCheck` threads through async calls without ceremony. The thread-local
 * scope has no analogue and is not reproduced.
 */
import { isNotRetryableError, isRetryableError, ProviderError } from './errors.js';

export type LogCallback = ((level: string, message: string) => void) | null;
export type CancelCheck = (() => boolean) | null;

/**
 * A cancel was requested during a backoff.
 *
 * Callers must treat it as an orderly stop rather than a provider failure: no
 * retry, no fallback.
 */
export class CancelledRetryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CancelledRetryError';
  }
}

export interface RetryConfig {
  max_retries?: number;
  backoff_seconds?: number[];
  respect_retry_after?: boolean;
}

/** Sleep in slices so a cancel is noticed within ~500ms rather than ~32s. */
async function interruptibleSleep(
  totalSeconds: number,
  cancelCheck: CancelCheck,
  stepSeconds = 0.5,
): Promise<void> {
  const sleep = (s: number): Promise<void> =>
    new Promise((resolve) => {
      setTimeout(resolve, s * 1000);
    });

  if (cancelCheck === null) {
    await sleep(totalSeconds);
    return;
  }
  let remaining = Math.max(0, totalSeconds);
  while (remaining > 0) {
    if (cancelCheck()) throw new CancelledRetryError('cancel requested during backoff');
    const slice = remaining > stepSeconds ? stepSeconds : remaining;
    await sleep(slice);
    remaining -= slice;
  }
}

/**
 * Call `fn` with retry on retryable provider errors.
 *
 * Returns `fn`'s result, or throws the last retryable error once the ladder is
 * exhausted. A non-retryable error is rethrown immediately.
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  retryConfig: RetryConfig,
  opts: { logCallback?: LogCallback; cancelCheck?: CancelCheck } = {},
): Promise<T> {
  const maxRetries = retryConfig.max_retries ?? 3;
  const backoff = retryConfig.backoff_seconds ?? [2, 8, 32];
  const respectRetryAfter = retryConfig.respect_retry_after ?? true;
  const logCallback = opts.logCallback ?? null;
  const cancelCheck = opts.cancelCheck ?? null;

  let lastError: unknown = null;

  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    // Checked before each attempt so a cancel requested while the previous call
    // was in flight prevents both another call and another sleep.
    if (cancelCheck !== null && cancelCheck()) {
      throw new CancelledRetryError('cancel requested before retry attempt');
    }

    try {
      return await fn();
    } catch (e) {
      if (isNotRetryableError(e)) throw e;
      if (!isRetryableError(e)) throw e;
      lastError = e;

      if (attempt >= maxRetries) break;

      let wait = attempt < backoff.length ? backoff[attempt]! : backoff.at(-1)!;
      // The provider's own Retry-After wins over our ladder: it knows when its
      // quota resets and we do not.
      if (respectRetryAfter && e instanceof ProviderError && e.retryAfter !== null) {
        wait = e.retryAfter;
      }

      logCallback?.(
        'warning',
        `Retry ${attempt + 1}/${maxRetries} after ${(e as Error).name}: ` +
          `${(e as Error).message} — waiting ${wait}s`,
      );
      await interruptibleSleep(wait, cancelCheck);
    }
  }

  throw lastError;
}
