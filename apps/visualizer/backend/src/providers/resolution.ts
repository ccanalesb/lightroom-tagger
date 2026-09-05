/**
 * The single provider/model resolution seam — one precedence ladder per kind.
 *
 * Describe, scoring, and the UI must share one ladder so the model the user picks
 * is the model that runs.
 */
import { getDescriptionModel } from '../config.js';
import { ModelUnavailableError } from './errors.js';
import { ProviderRegistry } from './registry.js';

/** Only one resolution kind survives; scoring shares the describe ladder. */
export type Kind = 'description';

export interface ResolvedModel {
  providerId: string;
  model: string;
  registry: ProviderRegistry;
}

/**
 * `DESCRIPTION_VISION_MODEL` beats `VISION_MODEL`.
 *
 * Both are process-level configuration only. The describe route passes an explicit
 * `model` argument instead of mutating env vars per request.
 */
function modelFromEnv(): string | null {
  if (process.env.DESCRIPTION_VISION_MODEL !== undefined) {
    return process.env.DESCRIPTION_VISION_MODEL;
  }
  return process.env.VISION_MODEL || null;
}

function resolveProvider(
  registry: ProviderRegistry,
  kind: Kind,
  providerId: string | null,
): string | null {
  if (providerId) return providerId;
  const provider = registry.defaults[kind]?.provider;
  if (provider) return provider;
  // Nothing configured: the head of the fallback order is the best guess.
  return registry.fallbackOrder[0] ?? null;
}

async function resolveModelName(
  registry: ProviderRegistry,
  kind: Kind,
  providerId: string,
  model: string | null,
): Promise<string> {
  if (model) return model;
  const envModel = modelFromEnv();
  if (envModel) return envModel;
  const defaultModel = registry.defaults[kind]?.model;
  if (defaultModel) return defaultModel;
  const configModel = getDescriptionModel();
  if (configModel) return configModel;

  const models = await registry.listModels(providerId);
  if (models.length === 0) {
    throw new ModelUnavailableError(`No models available for provider '${providerId}'`, {
      provider: providerId,
    });
  }
  return models[0]!.id;
}

/** Resolve provider and model using the documented precedence ladder. */
export async function resolveModel(
  opts: {
    kind?: Kind;
    providerId?: string | null;
    model?: string | null;
    registry?: ProviderRegistry;
  } = {},
): Promise<ResolvedModel> {
  const kind = opts.kind ?? 'description';
  const registry = opts.registry ?? new ProviderRegistry();

  const providerId = resolveProvider(registry, kind, opts.providerId ?? null);
  if (providerId === null) {
    throw new ModelUnavailableError(
      'No provider configured — set defaults or fallback_order in providers.json',
    );
  }

  return {
    providerId,
    model: await resolveModelName(registry, kind, providerId, opts.model ?? null),
    registry,
  };
}
