/**
 * Explicit command registry for the CLI, and the original of the pattern
 * `jobs/registry.ts` follows (ADR-0006).
 *
 * One list, greppable, no decorators and no auto-discovery: adding a command is
 * a visible edit here rather than a side effect of importing a module. The flags
 * live beside the command instead of in an `add_arguments` callback, because a
 * declarative list is all seven of them ever needed.
 *
 * `handler` was nullable while the port was in progress, so a declared but
 * unwritten command could say so instead of reading as a typo. All seven now
 * dispatch, so it is not.
 */
import type { LibraryConfig } from '../config.js';
import type { FlagSpec, ParsedArgs } from './parse.js';
import { cmdScan, cmdSync } from './commands/catalog.js';
import { cmdEnrichCatalog } from './commands/enrich.js';
import { cmdInit } from './commands/init.js';
import { cmdExport, cmdSearch, cmdStats } from './commands/query.js';

export interface CommandContext {
  args: ParsedArgs;
  config: LibraryConfig;
  /** Injected so tests can read what a command printed without capturing stdout. */
  out: (line: string) => void;
}

/**
 * A command returns its process exit code: 0 for success, 1 for failure.
 *
 * Six of the seven are synchronous and stay that way; `enrich-catalog` warms the
 * vision cache, which is filesystem and image work, so the return may be a
 * promise. `run` awaits either.
 */
export type CommandHandler = (ctx: CommandContext) => number | Promise<number>;

export interface CliCommand {
  name: string;
  help: string;
  flags: readonly FlagSpec[];
  handler: CommandHandler;
}

/** `--db`, which every command that touches the library declares. */
const DB_FLAG: FlagSpec = {
  name: 'db',
  kind: 'string',
  help: 'Path to SQLite database (overrides global)',
};

const CATALOG_FLAG: FlagSpec = {
  name: 'catalog',
  kind: 'string',
  help: 'Path to .lrcat file (overrides global)',
};

const LIMIT_FLAG: FlagSpec = { name: 'limit', kind: 'int', help: 'Limit results' };

export const COMMANDS: readonly CliCommand[] = [
  {
    name: 'scan',
    help: 'Scan catalog, index all images',
    flags: [
      CATALOG_FLAG,
      DB_FLAG,
      // Accepted and ignored, as in Python: both branches of `get_image_records`
      // run the same sequential loop, so the catalog has never been read in
      // parallel. Kept so an existing invocation is not rejected.
      { name: 'workers', kind: 'int', help: 'Parallel workers (no effect)' },
      { name: 'limit', kind: 'int', help: 'Limit number of images to process' },
    ],
    handler: cmdScan,
  },
  {
    name: 'sync',
    help: 'Incremental catalog sync — add missing images to library.db',
    flags: [CATALOG_FLAG, DB_FLAG],
    handler: cmdSync,
  },
  {
    name: 'search',
    help: 'Search indexed images',
    flags: [
      DB_FLAG,
      { name: 'keyword', kind: 'string', help: 'Search by keyword' },
      { name: 'rating', kind: 'int', help: 'Minimum rating (0-5)' },
      { name: 'color-label', kind: 'string', help: 'Filter by color label' },
      { name: 'date-start', kind: 'string', help: 'Start date (ISO format)' },
      { name: 'date-end', kind: 'string', help: 'End date (ISO format)' },
      LIMIT_FLAG,
    ],
    handler: cmdSearch,
  },
  {
    name: 'export',
    help: 'Export to JSON/CSV',
    flags: [
      DB_FLAG,
      { name: 'output', short: 'o', kind: 'string', help: 'Output file path', required: true },
      {
        name: 'format',
        kind: 'string',
        choices: ['json', 'csv'],
        help: 'Export format (default: json)',
      },
      { name: 'keyword', kind: 'string', help: 'Export only images matching keyword' },
      { name: 'rating', kind: 'int', help: 'Export only images with minimum rating' },
      LIMIT_FLAG,
    ],
    handler: cmdExport,
  },
  {
    name: 'init',
    help: 'Initialize database',
    flags: [DB_FLAG],
    handler: cmdInit,
  },
  {
    name: 'stats',
    help: 'Show database statistics',
    flags: [DB_FLAG],
    handler: cmdStats,
  },
  {
    name: 'enrich-catalog',
    help: 'Warm the vision cache for catalog images',
    flags: [
      DB_FLAG,
      // Both accepted and ignored. `--catalog` was already dead in Python:
      // `enrich_catalog_images` takes the path and never reads it. `--cache-only`
      // is now what the command always does, so the invocation people actually
      // run keeps working unchanged.
      { ...CATALOG_FLAG, help: 'Path to .lrcat file (no effect)' },
      { name: 'limit', kind: 'int', help: 'Limit number of images to process' },
      { name: 'cache-only', kind: 'boolean', help: 'Warm vision cache only (always on)' },
    ],
    handler: cmdEnrichCatalog,
  },
];
