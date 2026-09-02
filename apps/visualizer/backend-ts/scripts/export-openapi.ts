/**
 * Dump the OpenAPI document to stdout, for the frontend's type codegen.
 * Replaces `apps/visualizer/backend/scripts/export_openapi.py`.
 *
 * Nothing else in this process may write to stdout — the output must be parseable
 * JSON. Keep diagnostics on stderr.
 */
import { createApp } from '../src/app.js';
import { openApiDoc } from '../src/api/openapi.js';

const app = createApp();
const spec = app.getOpenAPI31Document(openApiDoc());
process.stdout.write(`${JSON.stringify(spec, null, 2)}\n`);
