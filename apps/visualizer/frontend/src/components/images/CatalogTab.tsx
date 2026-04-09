import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { PLACEHOLDER_CATALOG_VIEW } from '../../constants/strings';

interface CacheStats {
  total_images: number;
  cached_images: number;
  missing: number;
  cache_size_mb: number;
}

export function CatalogTab() {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const response = await fetch('/api/cache/status');
        const data = await response.json();
        if (!data.error) {
          setStats(data);
        }
      } catch (err) {
        console.error('Failed to load cache stats:', err);
      } finally {
        setLoading(false);
      }
    }
    loadStats();
  }, []);

  const cachePercentage = stats && stats.total_images > 0
    ? Math.round((stats.cached_images / stats.total_images) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card padding="md">
            <div className="text-center">
              <div className="text-2xl font-bold text-text">{stats.total_images.toLocaleString()}</div>
              <div className="text-xs text-text-secondary mt-1">Total Images</div>
            </div>
          </Card>
          <Card padding="md">
            <div className="text-center">
              <div className="text-2xl font-bold text-accent">{stats.cached_images.toLocaleString()}</div>
              <div className="text-xs text-text-secondary mt-1">Cached</div>
            </div>
          </Card>
          <Card padding="md">
            <div className="text-center">
              <div className="text-2xl font-bold text-warning">{stats.missing.toLocaleString()}</div>
              <div className="text-xs text-text-secondary mt-1">Missing</div>
            </div>
          </Card>
          <Card padding="md">
            <div className="text-center">
              <div className="text-2xl font-bold text-text">{stats.cache_size_mb.toFixed(0)} MB</div>
              <div className="text-xs text-text-secondary mt-1">Cache Size</div>
            </div>
          </Card>
        </div>
      )}

      <Card padding="lg">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Catalog Browser</CardTitle>
              {stats && (
                <div className="mt-2">
                  <Badge variant={cachePercentage === 100 ? 'success' : 'warning'}>
                    {cachePercentage}% Cached
                  </Badge>
                </div>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">Catalog Browser</h3>
            <p className="mt-1 text-sm text-text-secondary mb-6">
              {PLACEHOLDER_CATALOG_VIEW}
            </p>
            
            <div className="space-y-3 max-w-md mx-auto">
              {loading && (
                <p className="text-sm text-text-tertiary">Loading cache status...</p>
              )}
              {stats && stats.cached_images === 0 && (
                <div className="p-3 bg-surface rounded-base border border-border mb-4">
                  <p className="text-sm text-text-secondary">
                    ⚠️ No images cached yet. Visit <strong>Processing → Catalog Cache</strong> to rebuild the cache.
                  </p>
                </div>
              )}
              {stats && stats.missing > 0 && stats.cached_images > 0 && (
                <div className="p-3 bg-surface rounded-base border border-border mb-4">
                  <p className="text-sm text-text-secondary">
                    📊 {stats.missing.toLocaleString()} images not cached. Manage cache in <strong>Processing → Catalog Cache</strong>
                  </p>
                </div>
              )}
              <Link to="/processing?tab=cache">
                <Button variant="primary" fullWidth>
                  Manage Catalog Cache
                </Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
