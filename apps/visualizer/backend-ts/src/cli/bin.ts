#!/usr/bin/env node
/**
 * The `lightroom-tagger` executable. Everything it does lives in `main.ts`, so
 * that tests can call `run` without a subprocess and without this file's
 * `process.exitCode` side effect.
 */
import { run } from './main.js';

process.exitCode = run(process.argv.slice(2));
