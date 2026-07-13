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
const backendRoot = join(frontendRoot, '..', 'backend');
const outFile = join(frontendRoot, 'src', 'types', 'api.gen.ts');
const specFile = join(frontendRoot, '.openapi', 'openapi.json');

mkdirSync(dirname(specFile), { recursive: true });

const python = process.env.PYTHON ?? join(backendRoot, '..', '..', '..', '.venv', 'bin', 'python');
const exportScript = join(backendRoot, 'scripts', 'export_openapi.py');

const specJson = execFileSync(python, [exportScript], {
  cwd: backendRoot,
  encoding: 'utf8',
  env: { ...process.env, FLASK_DEBUG: 'true' },
});

writeFileSync(specFile, specJson);

execFileSync(
  'npx',
  ['openapi-typescript', specFile, '-o', outFile],
  { cwd: frontendRoot, stdio: 'inherit' },
);

console.log(`Wrote ${outFile}`);
