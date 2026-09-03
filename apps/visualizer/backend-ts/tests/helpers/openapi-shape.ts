/**
 * Reduce an OpenAPI schema to a comparable shape.
 *
 * The TypeScript and Flask documents cannot be compared field-for-field, because
 * two differences are unavoidable and neither is a contract change:
 *
 *   - **schema names.** spectree hashed every model name by content and duplicated
 *     nested models per parent, so the same `CatalogImage` appears three times as
 *     `CatalogListResponse.573ec44.CatalogImage`,
 *     `CatalogSimilarResponse.573ec44.CatalogImage` and
 *     `StackMembersResponse.b12c71e.CatalogImage`. Zod emits one shared
 *     `CatalogImage` and `$ref`s it. Names are therefore resolved away entirely and
 *     only the resolved structure is compared.
 *   - **spelling of the same constraint.** `int | None` is `anyOf: [integer, null]`
 *     from pydantic and may be `type: [integer, null]` from Zod; both mean the same
 *     thing, so both normalize to the same union.
 *
 * Annotations that carry no type information (`title`, `description`, `default`,
 * `examples`) and numeric bounds Zod adds to `z.int()` are dropped: they do not
 * change what `openapi-typescript` generates.
 */

export type Shape =
  | { t: 'object'; props: Record<string, Shape>; required: string[]; open: boolean }
  | { t: 'array'; items: Shape }
  | { t: 'union'; of: Shape[] }
  | { t: 'scalar'; type: string; const?: string }
  | { t: 'any' }
  | { t: 'cycle' };

export interface OpenApiDoc {
  paths?: Record<string, Record<string, unknown>>;
  components?: { schemas?: Record<string, unknown> };
}

type RawSchema = Record<string, unknown>;

/** Stable string form, used for equality and for sorting union members. */
export function canonical(shape: Shape): string {
  const sortKeys = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(sortKeys);
    if (v && typeof v === 'object') {
      return Object.fromEntries(
        Object.entries(v as Record<string, unknown>)
          .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
          .map(([k, val]) => [k, sortKeys(val)]),
      );
    }
    return v;
  };
  return JSON.stringify(sortKeys(shape));
}

function refName(ref: string): string {
  return ref.replace('#/components/schemas/', '');
}

/**
 * Normalize `schema` against the document it came from.
 *
 * `seen` tracks `$ref` names on the current path so a self-referential model
 * terminates instead of recursing forever.
 */
export function shapeOf(schema: unknown, doc: OpenApiDoc, seen: Set<string> = new Set()): Shape {
  if (schema === true || schema === undefined || schema === null) return { t: 'any' };
  if (typeof schema !== 'object') return { t: 'any' };

  const s = schema as RawSchema;

  if (typeof s.$ref === 'string') {
    const name = refName(s.$ref);
    if (seen.has(name)) return { t: 'cycle' };
    const target = doc.components?.schemas?.[name];
    if (target === undefined) return { t: 'any' };
    return shapeOf(target, doc, new Set([...seen, name]));
  }

  // `allOf` here is never a real intersection: it is how a `$ref` gets extra
  // annotations attached. Zod renders a nullable registered object as
  // `allOf: [{$ref}, {type: ['object','null']}]`, and pydantic renders the same
  // thing as `anyOf: [{$ref}, {type: null}]`. Take the substantive member and
  // carry the nullability across.
  if (Array.isArray(s.allOf)) {
    const members = s.allOf.map((m) => shapeOf(m, doc, seen));
    const substantive =
      members.find((m) => m.t === 'object' && Object.keys(m.props).length > 0) ??
      members.find((m) => m.t === 'array' || m.t === 'cycle') ??
      members.find((m) => m.t === 'scalar' && m.type !== 'null' && m.type !== 'object') ??
      members[0] ??
      ({ t: 'any' } as Shape);
    const nullable = members.some(
      (m) =>
        (m.t === 'scalar' && m.type === 'null') ||
        (m.t === 'union' && m.of.some((o) => o.t === 'scalar' && o.type === 'null')),
    );
    return nullable ? union([substantive, { t: 'scalar', type: 'null' }]) : substantive;
  }

  const variants = (s.anyOf ?? s.oneOf) as unknown[] | undefined;
  if (Array.isArray(variants)) {
    return union(variants.map((v) => shapeOf(v, doc, seen)));
  }

  if (Array.isArray(s.type)) {
    // `type: ['array', 'null']` is Zod's spelling of what pydantic writes as
    // `anyOf: [{type: array, items: ...}, {type: null}]`. Re-normalize each member
    // against the *whole* schema so `properties` / `items` are not lost — but the
    // `null` member must not inherit them, or `['array','null']` collapses to a
    // plain array and the nullability disappears from the comparison.
    return union(
      (s.type as string[]).map((t) =>
        t === 'null' ? ({ t: 'scalar', type: 'null' } as Shape) : shapeOf({ ...s, type: t }, doc, seen),
      ),
    );
  }

  // `'items' in s` / `'properties' in s` are fallbacks for a schema with no
  // explicit `type`; they must not override an explicit one.
  if (s.type === 'array' || (s.type === undefined && 'items' in s)) {
    return { t: 'array', items: shapeOf(s.items, doc, seen) };
  }

  if (s.type === 'object' || (s.type === undefined && 'properties' in s)) {
    const properties = (s.properties ?? {}) as Record<string, unknown>;
    const props: Record<string, Shape> = {};
    for (const [k, v] of Object.entries(properties)) props[k] = shapeOf(v, doc, seen);
    return {
      t: 'object',
      props,
      required: [...((s.required as string[] | undefined) ?? [])].sort(),
      // `extra='forbid'` / `.strict()` both render as `additionalProperties: false`.
      open: s.additionalProperties !== false,
    };
  }

  if (typeof s.type === 'string') {
    const out: Shape = { t: 'scalar', type: s.type };
    // `Literal[...]` renders as `const` in pydantic and as `const` (Zod 4) or a
    // single-item `enum` (older emitters); fold both into `const`.
    const constValue =
      'const' in s
        ? s.const
        : Array.isArray(s.enum) && s.enum.length === 1
          ? s.enum[0]
          : undefined;
    if (constValue !== undefined) out.const = JSON.stringify(constValue);
    return out;
  }

  // No `type` and no structure: `Any`.
  return { t: 'any' };
}

function union(options: Shape[]): Shape {
  // `Any | None` is just `Any`: pydantic spells it `anyOf: [{}, {type: null}]` and
  // Zod spells it `{}`, and both accept null. Collapsing keeps the two comparable.
  if (options.some((o) => o.t === 'any')) return { t: 'any' };
  const byCanonical = new Map(options.map((o) => [canonical(o), o]));
  const deduped = [...byCanonical.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  if (deduped.length === 1) return deduped[0]![1];
  return { t: 'union', of: deduped.map(([, o]) => o) };
}

export interface NormalizedParam {
  name: string;
  in: string;
  required: boolean;
}

export function paramsOf(operation: Record<string, unknown>): NormalizedParam[] {
  const raw = (operation.parameters as Record<string, unknown>[] | undefined) ?? [];
  return raw
    .map((p) => ({
      name: String(p.name),
      in: String(p.in),
      required: Boolean(p.required),
    }))
    .sort((a, b) => (`${a.in}:${a.name}` < `${b.in}:${b.name}` ? -1 : 1));
}

/** `{ '200': Shape, '400': Shape, ... }` for a single operation's JSON responses. */
export function responseShapes(
  operation: Record<string, unknown>,
  doc: OpenApiDoc,
): Record<string, Shape> {
  const responses = (operation.responses as Record<string, unknown> | undefined) ?? {};
  const out: Record<string, Shape> = {};
  for (const [status, resp] of Object.entries(responses)) {
    const content = (resp as { content?: Record<string, { schema?: unknown }> }).content;
    const json = content?.['application/json'];
    if (!json) continue;
    out[status] = shapeOf(json.schema, doc, new Set());
  }
  return out;
}

/** The request body shape, or `null` when the operation takes no JSON body. */
export function requestBodyShape(
  operation: Record<string, unknown>,
  doc: OpenApiDoc,
): Shape | null {
  const body = operation.requestBody as
    | { content?: Record<string, { schema?: unknown }> }
    | undefined;
  const json = body?.content?.['application/json'];
  if (!json) return null;
  return shapeOf(json.schema, doc, new Set());
}
