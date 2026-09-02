/**
 * Runtime configuration. Mirrors the Python backend's `config.py` (env-var driven)
 * plus the library's `config.yaml` loader from `lightroom_tagger/core/config.py`.
 *
 * Values are exposed as **getters**, read on each access. The Python module captured
 * `os.getenv` at import time, which meant tests had to reload the module to change a
 * path; reading lazily removes that whole class of test scaffolding.
 *
 * Load `.env` with `node --env-file=.env` rather than a dotenv dependency.
 */
import { readFileSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseYaml } from 'yaml';

const HERE = dirname(fileURLToPath(import.meta.url));
/** Monorepo root — `apps/visualizer/backend-ts/src` → four levels up. */
export const REPO_ROOT = resolve(HERE, '..', '..', '..', '..');

function expandUser(p: string): string {
  return p.startsWith('~') ? join(homedir(), p.slice(1)) : p;
}

/** Resolve a possibly-relative path against the repo root, expanding `~`. */
function resolvePath(p: string): string {
  const expanded = expandUser(p);
  return isAbsolute(expanded) ? expanded : resolve(REPO_ROOT, expanded);
}

// --- server -----------------------------------------------------------------

export const HOST_DEFAULT = 'localhost';
/**
 * 5001, not 5000: on macOS the AirPlay Receiver occupies :5000 and answers
 * requests, which presents as a broken backend. The Vite dev proxy targets 5001.
 */
export const PORT_DEFAULT = 5001;

export const config = {
  get HOST(): string {
    return process.env.FLASK_HOST ?? HOST_DEFAULT;
  },
  get PORT(): number {
    const raw = process.env.FLASK_PORT;
    const n = raw === undefined ? NaN : Number(raw);
    return Number.isFinite(n) ? n : PORT_DEFAULT;
  },
  get DEBUG(): boolean {
    return (process.env.FLASK_DEBUG ?? 'true').toLowerCase() === 'true';
  },
  get FRONTEND_ORIGINS(): string[] {
    return (
      process.env.FRONTEND_URL ?? 'http://localhost:5173,http://localhost:5174'
    ).split(',');
  },
  /** `visualizer.db` — jobs, logs, checkpoints. Separate from the library DB. */
  get VISUALIZER_DB(): string {
    return resolvePath(process.env.DATABASE_PATH ?? 'apps/visualizer/visualizer.db');
  },
  /** `library.db` — images, scores, descriptions, CLIP embeddings. */
  get LIBRARY_DB(): string {
    return resolvePath(process.env.LIBRARY_DB ?? 'library.db');
  },
  get THUMBNAIL_DIR(): string {
    return resolvePath(process.env.THUMBNAIL_DIR ?? 'apps/visualizer/thumbnails');
  },
} as const;

// --- library config.yaml ----------------------------------------------------

export interface LibraryConfig {
  catalogPath: string | null;
  dbPath: string | null;
  mountPoint: string | null;
  workers: number;
  visionModel: string | null;
  visionCacheDir: string;
  visionCacheEnabled: boolean;
  ollamaHost: string;
}

const CONFIG_DEFAULTS = {
  workers: 4,
  visionCacheDir: join(homedir(), '.cache', 'lightroom_tagger', 'vision'),
  visionCacheEnabled: true,
  ollamaHost: 'http://localhost:11434',
} as const;

/**
 * Read `config.yaml` from the repo root. Unknown keys are ignored rather than
 * rejected — the file is user-owned and may still carry keys from retired
 * features (#245).
 */
export function loadLibraryConfig(configPath = join(REPO_ROOT, 'config.yaml')): LibraryConfig {
  let raw: Record<string, unknown> = {};
  if (existsSync(configPath)) {
    raw = (parseYaml(readFileSync(configPath, 'utf8')) as Record<string, unknown>) ?? {};
  }
  const pathField = (k: string): string | null => {
    const v = raw[k];
    return typeof v === 'string' && v.length > 0 ? resolvePath(v) : null;
  };
  return {
    catalogPath: pathField('catalog_path'),
    dbPath: pathField('db_path'),
    // A mount point is an absolute filesystem location; never repo-relative.
    mountPoint: typeof raw.mount_point === 'string' ? expandUser(raw.mount_point) : null,
    workers: typeof raw.workers === 'number' ? raw.workers : CONFIG_DEFAULTS.workers,
    visionModel: typeof raw.vision_model === 'string' ? raw.vision_model : null,
    visionCacheDir:
      typeof raw.vision_cache_dir === 'string'
        ? expandUser(raw.vision_cache_dir)
        : CONFIG_DEFAULTS.visionCacheDir,
    visionCacheEnabled:
      typeof raw.vision_cache_enabled === 'boolean'
        ? raw.vision_cache_enabled
        : CONFIG_DEFAULTS.visionCacheEnabled,
    ollamaHost:
      typeof raw.ollama_host === 'string' ? raw.ollama_host : CONFIG_DEFAULTS.ollamaHost,
  };
}
