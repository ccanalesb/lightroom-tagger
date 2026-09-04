/** Lightroom config API models (`/api/config/*`). */
import { z } from '@hono/zod-openapi';

export const ConfigCatalogGetResponse = z
  .object({
    catalog_path: z.string(),
    resolved_path: z.string(),
    exists: z.boolean(),
  })
  .strict()
  .openapi('ConfigCatalogGetResponse');

export const ConfigCatalogPutRequest = z
  .object({ catalog_path: z.string() })
  .strict()
  .openapi('ConfigCatalogPutRequest');

export const ConfigCatalogPutResponse = z
  .object({
    catalog_path: z.string(),
    ok: z.boolean(),
  })
  .strict()
  .openapi('ConfigCatalogPutResponse');

export const ConfigStackDetectionGetResponse = z
  .object({ stack_burst_delta_ms: z.int() })
  .strict()
  .openapi('ConfigStackDetectionGetResponse');

export const ConfigStackDetectionPutRequest = z
  .object({ stack_burst_delta_ms: z.int() })
  .strict()
  .openapi('ConfigStackDetectionPutRequest');

export const ConfigStackDetectionPutResponse = z
  .object({
    stack_burst_delta_ms: z.int(),
    ok: z.boolean(),
  })
  .strict()
  .openapi('ConfigStackDetectionPutResponse');
