# ADR-0007: One provider/model resolution ladder

## Status
Accepted (2026-07)

## Context
"Which provider and model for this request?" was answered two incompatible ways:
providers.json `defaults` (scoring, NL search, description, vision-compare) and
config.yaml `vision_model` via `config.get_vision_model()` (matcher, standalone
script). The logic was duplicated across ~5 sites, `ProviderRegistry` was built 3×
per vision comparison, and the "no default provider" case diverged (some paths fell
back to `fallback_order[0]`, others raised).

## Decision
A single seam, `provider_resolution.resolve_model(kind, provider_id, model, registry)`,
returns `ResolvedModel(provider_id, model, registry)` and applies one precedence
ladder per kind, first non-empty wins:

 explicit arg > env (VISION_MODEL / DESCRIPTION_VISION_MODEL)
 > providers.json defaults[kind] > config.yaml vision_model > fallback_order[0]

Model strings from the upper rungs are trusted as-is; only a fully unresolved model
falls to `list_models(provider)[0]`. `ModelUnavailableError` is raised only when no
provider or no model can be produced. The registry is constructed once per operation
and reused (no process-wide singleton — the visualizer mutates providers.json defaults
at runtime, so a cached instance could go stale). `ProviderRegistry` stays a pure
providers.json adapter; the config-spanning logic lives only in `provider_resolution`.

## Consequences
- Uniform behaviour; the ladder is unit-testable via an injected registry + monkeypatched env/config.
- Two intentional behaviour shifts: text/scoring/description paths now honour the env
 overrides; the matcher now prefers providers.json defaults when set.
- Matcher dispatch/token-escalation is deliberately NOT consolidated here (see the
 VisionComparator candidate) — only model/provider selection is routed through the seam.
