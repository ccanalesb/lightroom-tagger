/**
 * Vision calls against OpenAI-compatible providers.
 * Port of `core/vision_client.py` and `core/vision_client_ollama.py`.
 *
 * The Python module wrapped the `openai` SDK and mapped its exception classes
 * onto the `ProviderError` hierarchy. Here the requests are plain `fetch` and the
 * mapping is from HTTP status, which is what the SDK's classes encode anyway —
 * `RateLimitError` is 429, `AuthenticationError` is 401/403, and so on. Same
 * reasoning as the registry: three endpoints do not justify the dependency.
 *
 * Ollama gets special treatment, and it is not cosmetic. It serves an
 * OpenAI-compatible surface at `/v1`, but only its native `/api/chat` honours the
 * `think` toggle. Through the compat endpoint `think` is silently ignored, so a
 * thinking model (kimi-k2.6) burns its entire output-token budget on the
 * reasoning channel and returns empty content. Routing Ollama natively with
 * `think: false` yields the actual answer, and is a harmless no-op for
 * non-thinking models.
 */
import { readFile } from 'node:fs/promises';
import { basename } from 'node:path';
import {
  AuthenticationError,
  ContextLengthError,
  InvalidRequestError,
  ModelUnavailableError,
  PayloadTooLargeError,
  ProviderConnectionError,
  ProviderError,
  ProviderTimeoutError,
  RateLimitError,
} from './errors.js';
import type { LogCallback } from './retry.js';

/** A resolved provider endpoint: everything a request needs and nothing more. */
export interface ProviderClient {
  providerId: string;
  baseUrl: string;
  apiKey: string;
  extraHeaders: Record<string, string>;
  timeoutMs: number;
}

interface ChatMessageContentPart {
  type: 'text' | 'image_url';
  text?: string;
  image_url?: { url: string };
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string | ChatMessageContentPart[];
}

async function encodeImage(path: string): Promise<string> {
  return (await readFile(path)).toString('base64');
}

function imageUrlPart(b64: string): ChatMessageContentPart {
  return { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${b64}` } };
}

/**
 * Map an HTTP failure onto the `ProviderError` hierarchy.
 *
 * The body text is inspected as well as the status, because providers disagree
 * about which 400 means "context too long" versus "bad model name", and the two
 * take different paths — one escalates `max_tokens`, the other aborts.
 */
function mapHttpError(
  status: number,
  body: string,
  headers: Headers,
  ctx: { provider: string | null; model: string | null },
): ProviderError {
  const retryAfterRaw = headers.get('retry-after');
  const parsed = retryAfterRaw === null ? Number.NaN : Number.parseFloat(retryAfterRaw);
  const retryAfter = Number.isFinite(parsed) ? parsed : null;
  const opts = { ...ctx, retryAfter };
  const msg = `${status}: ${body.slice(0, 500)}`;
  const lower = body.toLowerCase();

  if (status === 429) return new RateLimitError(msg, opts);
  if (status === 401 || status === 403) return new AuthenticationError(msg, ctx);
  if (status === 413) return new PayloadTooLargeError(msg, ctx);
  if (status === 400) {
    if (
      lower.includes('context length') ||
      lower.includes('too many tokens') ||
      lower.includes('maximum') ||
      lower.includes('budget_tokens') ||
      lower.includes('thinking')
    ) {
      return new ContextLengthError(msg, ctx);
    }
    return new InvalidRequestError(msg, ctx);
  }
  if (
    lower.includes('multimodal') ||
    lower.includes('image_url') ||
    lower.includes('modality')
  ) {
    return new InvalidRequestError(msg, ctx);
  }
  if (status === 503) return new ModelUnavailableError(msg, ctx);
  return new ProviderError(msg, ctx);
}

/** Map a transport-level failure — no HTTP response was received. */
function mapTransportError(
  e: unknown,
  ctx: { provider: string | null; model: string | null },
): ProviderError {
  const message = e instanceof Error ? e.message : String(e);
  if (e instanceof Error && (e.name === 'TimeoutError' || e.name === 'AbortError')) {
    return new ProviderTimeoutError(message, ctx);
  }
  // Refused, DNS failure, TLS failure: permanent for this provider.
  return new ProviderConnectionError(message, ctx);
}

async function postJson(
  client: ProviderClient,
  path: string,
  body: unknown,
  model: string,
): Promise<unknown> {
  const base = client.baseUrl.replace(/\/+$/, '');
  const ctx = { provider: client.providerId, model };
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${client.apiKey}`,
        'Content-Type': 'application/json',
        ...client.extraHeaders,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(client.timeoutMs),
    });
  } catch (e) {
    throw mapTransportError(e, ctx);
  }
  if (!res.ok) {
    throw mapHttpError(res.status, await res.text(), res.headers, ctx);
  }
  return res.json();
}

/** Ollama's native `/api/chat` URL, derived from its OpenAI-compat base. */
export function nativeChatUrl(baseUrl: string): string {
  let trimmed = baseUrl.replace(/\/+$/, '');
  if (trimmed.endsWith('/v1')) trimmed = trimmed.slice(0, -'/v1'.length);
  return `${trimmed}/api/chat`;
}

export function isOllamaClient(client: ProviderClient): boolean {
  return client.providerId === 'ollama';
}

/**
 * Split OpenAI-style content into Ollama's `(text, images)` shape.
 *
 * Ollama's native API wants the bare base64 payload in a separate `images` array
 * rather than a data URL inside the content parts.
 */
export function contentToNative(
  content: string | ChatMessageContentPart[],
): { text: string; images: string[] } {
  if (typeof content === 'string') return { text: content, images: [] };
  const textChunks: string[] = [];
  const images: string[] = [];
  for (const part of content) {
    if (part.type === 'text') textChunks.push(String(part.text ?? ''));
    else if (part.type === 'image_url') {
      const url = part.image_url?.url ?? '';
      const marker = 'base64,';
      const at = url.indexOf(marker);
      if (at !== -1) images.push(url.slice(at + marker.length));
    }
  }
  return { text: textChunks.join('\n'), images };
}

/** One turn through Ollama's native chat endpoint, so `think` is honoured. */
async function nativeChat(
  client: ProviderClient,
  model: string,
  messages: readonly ChatMessage[],
  opts: { maxTokens: number; think: boolean },
): Promise<string> {
  const ctx = { provider: client.providerId, model };
  const nativeMessages = messages.map((m) => {
    const { text, images } = contentToNative(m.content);
    return images.length > 0
      ? { role: m.role, content: text, images }
      : { role: m.role, content: text };
  });

  let res: Response;
  try {
    res = await fetch(nativeChatUrl(client.baseUrl), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...client.extraHeaders },
      body: JSON.stringify({
        model,
        messages: nativeMessages,
        stream: false,
        think: opts.think,
        options: { num_predict: opts.maxTokens },
      }),
      signal: AbortSignal.timeout(client.timeoutMs),
    });
  } catch (e) {
    throw mapTransportError(e, ctx);
  }
  if (!res.ok) throw mapHttpError(res.status, await res.text(), res.headers, ctx);

  const body = (await res.json()) as { message?: { content?: string } };
  return body.message?.content ?? '';
}

interface ChatCompletion {
  choices?: { message?: { content?: string | null } }[];
}

/**
 * Generate a structured description for one image. Returns the raw text.
 *
 * `think` defaults false because that is the reliable structured-JSON path;
 * `maxTokens` bounds the budget, and thinking needs a larger one or the answer
 * truncates before the JSON closes.
 */
export async function generateDescription(
  client: ProviderClient,
  model: string,
  imagePath: string,
  opts: {
    logCallback?: LogCallback;
    userPrompt?: string | null;
    think?: boolean;
    maxTokens?: number;
    fallbackPrompt: string;
  },
): Promise<string> {
  const maxTokens = opts.maxTokens ?? 2048;
  const think = opts.think ?? false;
  const imgB64 = await encodeImage(imagePath);
  const textPrompt =
    opts.userPrompt && opts.userPrompt.trim() ? opts.userPrompt.trim() : opts.fallbackPrompt;

  const messages: ChatMessage[] = [
    {
      role: 'user',
      content: [{ type: 'text', text: textPrompt }, imageUrlPart(imgB64)],
    },
  ];

  let raw: string;
  if (isOllamaClient(client)) {
    raw = await nativeChat(client, model, messages, { maxTokens, think });
  } else {
    const body = (await postJson(
      client,
      '/chat/completions',
      { model, messages, max_tokens: maxTokens },
      model,
    )) as ChatCompletion;
    raw = body.choices?.[0]?.message?.content ?? '';
  }

  opts.logCallback?.('debug', `[describe] ${basename(imagePath)} -> ${raw.length} chars`);
  return raw;
}

/** A text-only chat completion, with no images. */
export async function completeChatText(
  client: ProviderClient,
  model: string,
  opts: { system: string; user: string; maxTokens?: number; temperature?: number },
): Promise<string> {
  const body = (await postJson(
    client,
    '/chat/completions',
    {
      model,
      messages: [
        { role: 'system', content: opts.system },
        { role: 'user', content: opts.user },
      ],
      max_tokens: opts.maxTokens ?? 512,
      temperature: opts.temperature ?? 0,
      // Claude models bill reasoning tokens even for a repair call, and this
      // path only ever needs mechanical output.
      ...(model.toLowerCase().includes('claude')
        ? { extra_body: { reasoning_effort: 'none' } }
        : {}),
    },
    model,
  )) as ChatCompletion;
  return body.choices?.[0]?.message?.content ?? '';
}
