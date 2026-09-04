/**
 * The `lightroom-tagger` program; `bin.ts` is the executable that calls it.
 *
 * It lives under the visualizer backend rather than in a package of its own
 * because it is the same program: config loader, `library.db` seam, Lightroom
 * reader and catalog sync are all here already, and a second package would
 * either duplicate them or depend on this one.
 *
 * Every failure leaves as `Error: …` on stdout and exit 1 — not stderr, which is
 * where Python does not put it either, and scripts have been reading stdout for
 * as long as the command has existed.
 */
import { config as runtimeConfig, loadLibraryConfig, type LibraryConfig } from '../config.js';
import { CliError } from './library-db.js';
import { helpText, parseArgv, preparseConfigPath, UsageError } from './parse.js';
import { COMMANDS, type CommandContext } from './registry.js';

export interface RunOptions {
  /** Where output goes. Defaults to stdout; tests pass a collector. */
  out?: (line: string) => void;
  /** Config already loaded, for a caller that has one. */
  config?: LibraryConfig;
}

/**
 * Run one command line and return its exit code.
 *
 * Exported separately from `main` so tests drive the whole program — parsing,
 * dispatch, error mapping — without a subprocess or a captured stdout.
 */
export async function run(argv: readonly string[], opts: RunOptions = {}): Promise<number> {
  const out = opts.out ?? ((line: string) => process.stdout.write(`${line}\n`));

  let config: LibraryConfig;
  try {
    config =
      opts.config ??
      loadLibraryConfig(preparseConfigPath(argv, runtimeConfig.LT_CONFIG_YAML));
  } catch (e) {
    out(`Error loading config: ${e instanceof Error ? e.message : String(e)}`);
    return 1;
  }

  let args;
  try {
    args = parseArgv(argv, COMMANDS);
  } catch (e) {
    if (!(e instanceof UsageError)) throw e;
    out(helpText(COMMANDS));
    return 1;
  }

  const command = COMMANDS.find((c) => c.name === args.command)!;
  const ctx: CommandContext = { args, config, out };
  try {
    return await command.handler(ctx);
  } catch (e) {
    // Every throw, not just `CliError`: Python's `map_cli_errors` catches bare
    // `Exception`, so a command that fails on a corrupt database reports it the
    // same way as one that fails on a missing flag.
    out(`Error: ${e instanceof CliError || e instanceof Error ? e.message : String(e)}`);
    return 1;
  }
}
