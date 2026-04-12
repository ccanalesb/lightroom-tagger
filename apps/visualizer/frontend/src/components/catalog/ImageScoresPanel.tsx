import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_DEFAULT_URL } from '../../constants/strings';
import { Badge } from '../ui/Badge';

const API_URL = import.meta.env.VITE_API_URL || API_DEFAULT_URL;

export interface ImageScoreRow {
  id?: number;
  image_key: string;
  image_type: string;
  perspective_slug: string;
  score: number;
  rationale: string;
  model_used: string;
  prompt_version: string;
  scored_at: string;
  is_current: boolean;
  repaired_from_malformed: boolean;
}

async function scoresJsonRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && typeof (body as { error?: unknown }).error === 'string') {
        detail = (body as { error: string }).error;
      }
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json();
}

/** Mirrors `ScoresAPI` from `api.ts` (06-02); local until shared client lands. */
const ScoresAPI = {
  getCurrent: (imageKey: string, params?: { image_type?: 'catalog' | 'instagram' }) => {
    const sp = new URLSearchParams();
    if (params?.image_type) sp.set('image_type', params.image_type);
    const qs = sp.toString();
    return scoresJsonRequest<{ current: ImageScoreRow[] }>(
      `/scores/${encodeURIComponent(imageKey)}${qs ? `?${qs}` : ''}`,
    ).then((body) => body.current ?? []);
  },

  getHistory: (
    imageKey: string,
    params: { perspective_slug: string; image_type?: 'catalog' | 'instagram' },
  ) => {
    const sp = new URLSearchParams();
    sp.set('perspective_slug', params.perspective_slug);
    if (params.image_type) sp.set('image_type', params.image_type);
    return scoresJsonRequest<{ history: ImageScoreRow[] }>(
      `/scores/${encodeURIComponent(imageKey)}/history?${sp.toString()}`,
    ).then((body) => body.history ?? []);
  },
};

export interface ImageScoresPanelProps {
  imageKey: string;
  imageType?: 'catalog' | 'instagram';
  /** Increment to refetch current scores (e.g. after a scoring job completes). */
  reloadToken?: number;
  /** Optional map slug → display name from `PerspectivesAPI.list`. */
  perspectiveLabels?: Record<string, string>;
}

function formatScoredAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function uniqueCurrentBySlug(rows: ImageScoreRow[]): ImageScoreRow[] {
  const map = new Map<string, ImageScoreRow>();
  for (const row of rows) {
    if (!map.has(row.perspective_slug)) {
      map.set(row.perspective_slug, row);
    }
  }
  return [...map.values()].sort((a, b) => a.perspective_slug.localeCompare(b.perspective_slug));
}

export default function ImageScoresPanel({
  imageKey,
  imageType = 'catalog',
  reloadToken = 0,
  perspectiveLabels,
}: ImageScoresPanelProps) {
  const [current, setCurrent] = useState<ImageScoreRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSlugs, setExpandedSlugs] = useState<Set<string>>(() => new Set());
  const [historyBySlug, setHistoryBySlug] = useState<Record<string, ImageScoreRow[]>>({});
  const [historyLoading, setHistoryLoading] = useState<Record<string, boolean>>({});
  const [historyError, setHistoryError] = useState<Record<string, string | null>>({});
  const prevExpandedRef = useRef<Set<string>>(new Set());
  const historyCacheRef = useRef(historyBySlug);
  historyCacheRef.current = historyBySlug;

  const rows = useMemo(() => uniqueCurrentBySlug(current), [current]);

  useEffect(() => {
    setExpandedSlugs(new Set());
    setHistoryBySlug({});
    setHistoryLoading({});
    setHistoryError({});
    prevExpandedRef.current = new Set();
  }, [imageKey, imageType]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    ScoresAPI.getCurrent(imageKey, { image_type: imageType })
      .then((data) => {
        if (!cancelled) {
          setCurrent(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(String(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [imageKey, imageType, reloadToken]);

  useEffect(() => {
    setExpandedSlugs(new Set());
    setHistoryBySlug({});
    setHistoryLoading({});
    setHistoryError({});
    prevExpandedRef.current = new Set();
  }, [reloadToken]);

  const fetchHistoryFor = useCallback(
    async (slug: string) => {
      if (historyCacheRef.current[slug] !== undefined) return;
      setHistoryLoading((h) => ({ ...h, [slug]: true }));
      setHistoryError((h) => ({ ...h, [slug]: null }));
      try {
        const hist = await ScoresAPI.getHistory(imageKey, {
          perspective_slug: slug,
          image_type: imageType,
        });
        setHistoryBySlug((c) => ({ ...c, [slug]: hist }));
      } catch (e) {
        setHistoryError((h) => ({ ...h, [slug]: String(e) }));
      } finally {
        setHistoryLoading((h) => ({ ...h, [slug]: false }));
      }
    },
    [imageKey, imageType],
  );

  useEffect(() => {
    const prev = prevExpandedRef.current;
    for (const slug of expandedSlugs) {
      if (!prev.has(slug)) {
        void fetchHistoryFor(slug);
      }
    }
    prevExpandedRef.current = new Set(expandedSlugs);
  }, [expandedSlugs, fetchHistoryFor]);

  const onToggleHistoryClick = useCallback((slug: string) => {
    setExpandedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }, []);

  if (loading) {
    return <p className="text-sm text-text-tertiary">Loading scores…</p>;
  }

  if (error) {
    return <p className="text-sm text-error">{error}</p>;
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm text-text-secondary">
        No critique scores for this image yet. Run scoring from the button below or use Processing →
        Descriptions to batch score.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {rows.map((row) => {
        const label = perspectiveLabels?.[row.perspective_slug] ?? row.perspective_slug;
        const expanded = expandedSlugs.has(row.perspective_slug);
        const histLoading = historyLoading[row.perspective_slug];
        const histErr = historyError[row.perspective_slug];
        const historyRows = historyBySlug[row.perspective_slug];

        return (
          <div
            key={row.perspective_slug}
            className="rounded-base border border-border bg-bg/40 p-3 space-y-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-text">{label}</span>
              <Badge variant="accent" className="tabular-nums">
                {row.score} / 10
              </Badge>
              <button
                type="button"
                onClick={() => onToggleHistoryClick(row.perspective_slug)}
                aria-expanded={expanded}
                className="ml-auto flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover transition-colors"
              >
                <svg
                  className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Version history
              </button>
            </div>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">{row.rationale}</p>
            <p className="text-xs text-text-tertiary">
              {row.model_used} · {row.prompt_version} · {formatScoredAt(row.scored_at)}
            </p>
            {row.repaired_from_malformed && (
              <p className="text-xs text-warning">Output was repaired before save</p>
            )}

            {expanded && (
              <div className="pt-2 border-t border-border space-y-2">
                {histLoading && (
                  <p className="text-xs text-text-tertiary">Loading history…</p>
                )}
                {histErr && <p className="text-xs text-error">{histErr}</p>}
                {!histLoading && !histErr && historyRows && historyRows.length === 0 && (
                  <p className="text-xs text-text-secondary">No prior versions.</p>
                )}
                {!histLoading &&
                  !histErr &&
                  historyRows &&
                  historyRows.map((h) => (
                    <div
                      key={`${h.perspective_slug}-${h.prompt_version}-${h.scored_at}-${h.id ?? ''}`}
                      className="flex flex-wrap items-center gap-2 text-xs text-text-secondary"
                    >
                      <span className="tabular-nums">{h.score} / 10</span>
                      <code className="text-[11px] bg-surface px-1.5 py-0.5 rounded border border-border">
                        {h.prompt_version}
                      </code>
                      <span>{formatScoredAt(h.scored_at)}</span>
                      {h.is_current ? (
                        <Badge variant="success">Latest</Badge>
                      ) : (
                        <Badge variant="default">Archived</Badge>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
