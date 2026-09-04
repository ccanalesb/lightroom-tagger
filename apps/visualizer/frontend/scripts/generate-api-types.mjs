#!/usr/bin/env node
/**
 * Dump backend OpenAPI (Jobs routes) and generate committed TypeScript types.
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, '..');
const backendRoot = join(frontendRoot, '..', 'backend-ts');
const outFile = join(frontendRoot, 'src', 'types', 'api.gen.ts');
const specFile = join(frontendRoot, '.openapi', 'openapi.json');

mkdirSync(dirname(specFile), { recursive: true });

// tsx directly, not `npm run export:openapi`: npm prints its own banner to
// stdout and the spec has to be the only thing there.
const specJson = execFileSync(
  join(backendRoot, 'node_modules', '.bin', 'tsx'),
  [join(backendRoot, 'scripts', 'export-openapi.ts')],
  { cwd: backendRoot, encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 },
);

writeFileSync(specFile, specJson);

execFileSync(
  'npx',
  ['openapi-typescript', specFile, '-o', outFile],
  { cwd: frontendRoot, stdio: 'inherit' },
);

console.log(`Wrote ${outFile}`);
