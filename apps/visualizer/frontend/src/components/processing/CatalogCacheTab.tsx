import { useCallback, useState } from 'react';
import { invalidateAll, useQuery } from '../../data';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/badges';
import { JobsAPI } from '../../services/api';
import {
  PROCESSING_EMBED_CATALOG_BODY,
  PROCESSING_EMBED_CATALOG_FAILED_PREFIX,
  PROCESSING_EMBED_CATALOG_QUEUED,
  PROCESSING_EMBED_CATALOG_START,
  PROCESSING_EMBED_CATALOG_STARTING,
  PROCESSING_EMBED_CATALOG_TITLE,
  PROCESSING_JOB_QUEUE_ROUTE,
  PROCESSING_OPEN_JOB_QUEUE,
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

export interface CatalogCacheTabProps {
  onJobEnqueued?: () => void;
  onOpenJobQueue?: () => void;
}

export function CatalogCacheTab({ onJobEnqueued, onOpenJobQueue }: CatalogCacheTabProps) {
  const [listRev, setListRev] = useState(0);
  const stats = useQuery(['catalog.cache.stats', listRev] as const, fetchCacheStats);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [embedStarting, setEmbedStarting] = useState(false);
  const [embedQueued, setEmbedQueued] = useState(false);
  const [embedError, setEmbedError] = useState<string | null>(null);

  const refreshStats = useCallback(() => {
    invalidateAll(['catalog.cache.stats']);
    setListRev((n) => n + 1);
  }, []);

  const handleRebuildCache = useCallback(async () => {
    setIsRebuilding(true);
    try {
      await JobsAPI.create('prepare_catalog', {});
      alert('Catalog cache rebuild started! Check Job Queue tab to monitor progress.');
      onJobEnqueued?.();
    } catch (err) {
      alert(`Failed to start rebuild: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsRebuilding(false);
    }
  }, [onJobEnqueued]);

  const handleStartEmbedJob = useCallback(async () => {
    setEmbedStarting(true);
    setEmbedQueued(false);
    setEmbedError(null);
    try {
      await JobsAPI.create('batch_embed_image', { image_type: 'catalog' });
      setEmbedQueued(true);
      onJobEnqueued?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setEmbedError(message);
    } finally {
      setEmbedStarting(false);
    }
  }, [onJobEnqueued]);

  const handleOpenJobQueue = useCallback(() => {
    if (onOpenJobQueue) {
      onOpenJobQueue();
      return;
    }
    window.location.assign(PROCESSING_JOB_QUEUE_ROUTE);
  }, [onOpenJobQueue]);

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

          <div className="mb-6 rounded-base border border-border bg-surface p-4">
            <h3 className="text-sm font-semibold text-text">{PROCESSING_EMBED_CATALOG_TITLE}</h3>
            <p className="mt-1 text-sm text-text-secondary">{PROCESSING_EMBED_CATALOG_BODY}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={handleStartEmbedJob}
                disabled={embedStarting}
              >
                {embedStarting ? PROCESSING_EMBED_CATALOG_STARTING : PROCESSING_EMBED_CATALOG_START}
              </Button>
              {embedQueued ? (
                <Button variant="secondary" size="sm" onClick={handleOpenJobQueue}>
                  {PROCESSING_OPEN_JOB_QUEUE}
                </Button>
              ) : null}
            </div>
            {embedQueued ? (
              <p className="mt-2 text-sm text-success" role="status">
                {PROCESSING_EMBED_CATALOG_QUEUED}
              </p>
            ) : null}
            {embedError ? (
              <p className="mt-2 text-sm text-error" role="status">
                {PROCESSING_EMBED_CATALOG_FAILED_PREFIX} {embedError}
              </p>
            ) : null}
          </div>

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

          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-text">Cache Progress</span>
              <span className="text-sm text-text-secondary">{cachePercentage}%</span>
            </div>
            <div className="w-full bg-surface rounded-full h-3 border border-border">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${cachePercentage}%`,
                  backgroundColor: cachePercentage === 100 ? 'var(--color-success)' : 'var(--color-accent)',
                }}
              />
            </div>
          </div>

          <div className="pt-4 space-y-2">
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={handleRebuildCache}
              disabled={isRebuilding}
            >
              {isRebuilding ? 'Starting Rebuild...' : 'Rebuild Catalog Cache'}
            </Button>
            <Button variant="secondary" size="md" fullWidth onClick={refreshStats}>
              Refresh Stats
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
