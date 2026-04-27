import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { invalidateAll, useQuery } from '../../data';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/badges';
import { AdvancedOptions } from '../matching/AdvancedOptions';
import { ImageTile, fromCatalogListRow } from '../image-view';
import { ImagesAPI, JobsAPI, type CatalogSimilarityGroup } from '../../services/api';
import { useMatchOptions } from '../../stores/matchOptionsContext';
import {
  ANALYZE_PRIMARY_BUTTON_STARTING,
  CACHE_REFRESH_BUTTON,
  CATALOG_CACHE_BUILD_CTA,
  CATALOG_CACHE_BUILD_SUCCESS,
  CATALOG_CACHE_EMBED_CATALOG_LABEL,
  CATALOG_CACHE_EMBED_CATALOG_IG_LABEL,
  CATALOG_CACHE_PREPARE_CATALOG_HELPER,
  CATALOG_CACHE_PREPARE_CATALOG_TITLE,
  CATALOG_CACHE_SIMILARITY_LABEL,
  CATALOG_CACHE_SIMILARITY_BEST_MATCH_PCT,
  CATALOG_CACHE_SIMILARITY_CANDIDATE_LABEL,
  CATALOG_CACHE_SIMILARITY_EMPTY,
  CATALOG_CACHE_SIMILARITY_PREVIEW_TITLE,
  CATALOG_CACHE_SIMILARITY_TOTAL_GROUPS_LABEL,
  CATALOG_CACHE_SIMILARITY_VIEW_ALL,
  CATALOG_CACHE_STACK_DETECT_LABEL,
  PROCESSING_JOB_QUEUE_ROUTE,
  PROCESSING_OPEN_JOB_QUEUE,
  MSG_FAILED_START_JOB,
} from '../../constants/strings';

interface CacheStats {
  total_images: number;
  cached_images: number;
  missing: number;
  cache_size_mb: number;
  cache_dir: string;
}

async function fetchCacheStats(): Promise<CacheStats> {
  const response = await fetch('/api/cache/status');
  const data = (await response.json()) as CacheStats & { error?: string };
  if (data.error) {
    throw new Error(data.error);
  }
  return data;
}

type AdvancedBusyKey =
  | 'embed_catalog'
  | 'embed_catalog_ig'
  | 'stack'
  | 'similarity'
  | 'prepare';

export interface CatalogCacheTabProps {
  onJobEnqueued?: () => void;
  onOpenJobQueue?: () => void;
}

export function CatalogCacheTab({ onJobEnqueued, onOpenJobQueue }: CatalogCacheTabProps) {
  const { options, updateOption, resetOptions, weightsError } = useMatchOptions();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [listRev, setListRev] = useState(0);
  const stats = useQuery(['catalog.cache.stats', listRev] as const, fetchCacheStats);
  const catalogSimilarity = useQuery(
    ['catalog.similarity.groups', { limit: 12, offset: 0 }] as const,
    () => ImagesAPI.listCatalogSimilarityGroups({ limit: 12, offset: 0 }),
  );

  const [buildStarting, setBuildStarting] = useState(false);
  const [buildSuccess, setBuildSuccess] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [advancedBusy, setAdvancedBusy] = useState<AdvancedBusyKey | null>(null);

  const anyBusy = buildStarting || advancedBusy !== null;

  const refreshStats = useCallback(() => {
    invalidateAll(['catalog.cache.stats']);
    setListRev((n) => n + 1);
  }, []);

  const handleOpenJobQueue = useCallback(() => {
    if (onOpenJobQueue) {
      onOpenJobQueue();
      return;
    }
    window.location.assign(PROCESSING_JOB_QUEUE_ROUTE);
  }, [onOpenJobQueue]);

  const handleBuildCatalogCache = useCallback(async () => {
    setBuildStarting(true);
    setBuildSuccess(false);
    setBuildError(null);
    try {
      await JobsAPI.create('catalog_cache_build', {});
      setBuildSuccess(true);
      onJobEnqueued?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : MSG_FAILED_START_JOB;
      setBuildError(message);
    } finally {
      setBuildStarting(false);
    }
  }, [onJobEnqueued]);

  const runAdvancedJob = useCallback(
    async (key: AdvancedBusyKey, type: string, metadata: Record<string, unknown>) => {
      setAdvancedBusy(key);
      try {
        await JobsAPI.create(type, metadata);
        if (key === 'similarity') {
          invalidateAll(['catalog.similarity.groups']);
        }
        onJobEnqueued?.();
      } catch (err) {
        const message = err instanceof Error ? err.message : MSG_FAILED_START_JOB;
        alert(`${MSG_FAILED_START_JOB}: ${message}`);
      } finally {
        setAdvancedBusy(null);
      }
    },
    [onJobEnqueued],
  );

  const cachePercentage =
    stats.total_images > 0 ? Math.round((stats.cached_images / stats.total_images) * 100) : 0;

  return (
    <div className="space-y-6">
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Catalog Vision Cache</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-secondary mb-6">
            The vision cache stores preprocessed Lightroom catalog images for fast AI comparison.
            Rebuilding the cache will process all catalog images and may take several minutes.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-surface rounded-base border border-border">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-text-secondary">Total Images</span>
                <Badge variant="default">{stats.total_images.toLocaleString()}</Badge>
              </div>
              <p className="text-xs text-text-tertiary">Images in Lightroom catalog</p>
            </div>

            <div className="p-4 bg-surface rounded-base border border-border">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-text-secondary">Cached Images</span>
                <Badge variant={cachePercentage === 100 ? 'success' : 'accent'}>
                  {stats.cached_images.toLocaleString()}
                </Badge>
              </div>
              <p className="text-xs text-text-tertiary">Processed for AI matching</p>
            </div>

            <div className="p-4 bg-surface rounded-base border border-border">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-text-secondary">Missing</span>
                <Badge variant={stats.missing > 0 ? 'warning' : 'success'}>
                  {stats.missing.toLocaleString()}
                </Badge>
              </div>
              <p className="text-xs text-text-tertiary">Not yet cached</p>
            </div>

            <div className="p-4 bg-surface rounded-base border border-border">
              <div className="flex items-start justify-between mb-2">
                <span className="text-sm text-text-secondary">Cache Size</span>
                <Badge variant="default">{stats.cache_size_mb.toFixed(1)} MB</Badge>
              </div>
              <p className="text-xs text-text-tertiary">Disk space used</p>
            </div>
          </div>

          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-text">Cache Progress</span>
              <span className="text-sm text-text-secondary">{cachePercentage}%</span>
            </div>
            <div className="w-full bg-surface rounded-full h-3 border border-border">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${cachePercentage}%`,
                  backgroundColor:
                    cachePercentage === 100 ? 'var(--color-success)' : 'var(--color-accent)',
                }}
              />
            </div>
          </div>

          <div className="space-y-3 mb-6">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={handleBuildCatalogCache}
              disabled={anyBusy}
            >
              {buildStarting ? ANALYZE_PRIMARY_BUTTON_STARTING : CATALOG_CACHE_BUILD_CTA}
            </Button>
            {buildSuccess ? (
              <div className="rounded-base border border-border bg-surface p-4 space-y-3">
                <p className="text-sm text-success" role="status">
                  {CATALOG_CACHE_BUILD_SUCCESS}
                </p>
                <Button variant="secondary" size="sm" type="button" onClick={handleOpenJobQueue}>
                  {PROCESSING_OPEN_JOB_QUEUE}
                </Button>
              </div>
            ) : null}
            {buildError ? (
              <p className="text-sm text-error" role="status">
                {MSG_FAILED_START_JOB}: {buildError}
              </p>
            ) : null}

            <CatalogSimilarityGroupsPreview
              groups={catalogSimilarity.items ?? []}
              total={catalogSimilarity.total}
            />
          </div>

          <AdvancedOptions
            isOpen={showAdvanced}
            onToggle={() => setShowAdvanced(!showAdvanced)}
            {...options}
            onProviderChange={(providerId, modelId) => {
              updateOption('providerId', providerId);
              updateOption('providerModel', modelId);
            }}
            onThresholdChange={(v) => updateOption('threshold', v)}
            onPhashWeightChange={(v) => updateOption('phashWeight', v)}
            onDescWeightChange={(v) => updateOption('descWeight', v)}
            onVisionWeightChange={(v) => updateOption('visionWeight', v)}
            maxWorkers={options.maxWorkers}
            onMaxWorkersChange={(v) => updateOption('maxWorkers', v)}
            onSkipUndescribedChange={(v) => updateOption('skipUndescribed', v)}
            weightsError={weightsError}
            onReset={resetOptions}
          >
            <div className="space-y-6">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={anyBusy}
                  onClick={() =>
                    runAdvancedJob('embed_catalog', 'batch_embed_image', { image_type: 'catalog' })
                  }
                >
                  {CATALOG_CACHE_EMBED_CATALOG_LABEL}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={anyBusy}
                  onClick={() =>
                    runAdvancedJob('embed_catalog_ig', 'batch_embed_image', {
                      image_type: 'catalog_and_instagram',
                    })
                  }
                >
                  {CATALOG_CACHE_EMBED_CATALOG_IG_LABEL}
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={anyBusy}
                  onClick={() => runAdvancedJob('stack', 'batch_stack_detect', {})}
                >
                  {CATALOG_CACHE_STACK_DETECT_LABEL}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={anyBusy}
                  onClick={() => runAdvancedJob('similarity', 'batch_catalog_similarity', {})}
                >
                  {CATALOG_CACHE_SIMILARITY_LABEL}
                </Button>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-text">{CATALOG_CACHE_PREPARE_CATALOG_TITLE}</h3>
                <p className="text-xs text-text-secondary leading-relaxed">{CATALOG_CACHE_PREPARE_CATALOG_HELPER}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  type="button"
                  disabled={anyBusy}
                  onClick={() => runAdvancedJob('prepare', 'prepare_catalog', {})}
                >
                  {CATALOG_CACHE_PREPARE_CATALOG_TITLE}
                </Button>
              </div>
            </div>
          </AdvancedOptions>

          <div className="pt-4">
            <Button variant="secondary" size="md" fullWidth onClick={refreshStats} disabled={anyBusy}>
              {CACHE_REFRESH_BUTTON}
            </Button>
          </div>

          <div className="mt-4 p-3 bg-surface rounded-base border border-border">
            <p className="text-xs text-text-tertiary">
              <strong>Cache Location:</strong> {stats.cache_dir}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CatalogSimilarityGroupsPreview({
  groups,
  total,
}: {
  groups: CatalogSimilarityGroup[]
  total?: number
}) {
  if (groups.length === 0) {
    return (
      <p className="rounded-base border border-border bg-surface p-4 text-sm text-text-secondary">
        {CATALOG_CACHE_SIMILARITY_EMPTY}
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-sm font-semibold text-text">{CATALOG_CACHE_SIMILARITY_PREVIEW_TITLE}</h3>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-secondary">
            {CATALOG_CACHE_SIMILARITY_TOTAL_GROUPS_LABEL(total ?? groups.length)}
          </span>
          <Link
            to={PROCESSING_JOB_QUEUE_ROUTE}
            className="text-xs font-medium text-accent hover:underline"
          >
            {CATALOG_CACHE_SIMILARITY_VIEW_ALL}
          </Link>
        </div>
      </div>
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.group_id} className="rounded-base border border-border bg-surface p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-text">
                {CATALOG_CACHE_SIMILARITY_BEST_MATCH_PCT(Math.round(group.best_similarity * 100))}
              </span>
              <span className="text-xs text-text-secondary">
                {CATALOG_CACHE_SIMILARITY_CANDIDATE_LABEL(group.candidate_count)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <ImageTile
                image={fromCatalogListRow(group.seed)}
                variant="strip"
                primaryScoreSource="catalog"
                onClick={() => {}}
              />
              {group.candidates.slice(0, 3).map((candidate) => (
                <div key={candidate.key} className="space-y-1">
                  <ImageTile
                    image={fromCatalogListRow(candidate)}
                    variant="strip"
                    primaryScoreSource="catalog"
                    onClick={() => {}}
                  />
                  <p className="text-center text-xs text-text-secondary">
                    {Math.round((candidate.similarity ?? 0) * 100)}%
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
