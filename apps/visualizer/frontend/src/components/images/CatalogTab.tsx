import { useEffect, useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';

export function CatalogTab() {
  const [checking, setChecking] = useState(true);
  const [hasCache, setHasCache] = useState(false);

  useEffect(() => {
    async function checkCache() {
      try {
        const response = await fetch('/api/catalog/status');
        const data = await response.json();
        setHasCache(Boolean(data.cached));
      } catch (err) {
        console.error('Failed to check catalog status:', err);
      } finally {
        setChecking(false);
      }
    }
    checkCache();
  }, []);

  if (checking) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-text-secondary">Checking catalog status...</div>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <div className="text-center py-12">
        <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-text">Catalog Browser</h3>
        <p className="mt-1 text-sm text-text-secondary mb-4">
          {hasCache
            ? 'Catalog browsing interface coming soon. Catalog cache is ready.'
            : 'Catalog needs to be prepared first. Run a prepare_catalog job from Processing.'}
        </p>
        {!hasCache && (
          <Button variant="primary" onClick={() => (window.location.href = '/processing')}>
            Go to Processing
          </Button>
        )}
      </div>
    </Card>
  );
}
