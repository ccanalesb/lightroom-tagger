import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { JobsAPI } from '../../services/api';

interface CacheStats {
  total_images: number;
  cached_images: number;
  missing: number;
  cache_size_mb: number;
  cache_dir: string;
}

export function CatalogCacheTab() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRebuilding, setIsRebuilding] = useState(false);

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/cache/status');
      const data = await response.json();
      if (data.error) {
        setError(data.error);
      } else {
        setStats(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cache stats');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleRebuildCache = useCallback(async () => {
    setIsRebuilding(true);
    try {
      await JobsAPI.create('prepare_catalog', {});
      alert('Catalog cache rebuild started! Check Job Queue tab to monitor progress.');
    } catch (err) {
      alert(`Failed to start rebuild: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsRebuilding(false);
    }
  }, []);

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">Loading cache stats...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-error">Error: {error}</div>
      </Card>
    );
  }

  if (!stats) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">No cache data available</div>
      </Card>
    );
  }

  const cachePercentage = stats.total_images > 0
    ? Math.round((stats.cached_images / stats.total_images) * 100)
    : 0;

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
            <Button variant="secondary" size="md" fullWidth onClick={loadStats}>
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
