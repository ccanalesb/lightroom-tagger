import { Suspense } from 'react';
import { Tabs, Tab } from '../components/ui/Tabs';
import { InstagramTab } from '../components/images/InstagramTab';
import { CatalogTab } from '../components/images/CatalogTab';
import { MatchesTab } from '../components/images/MatchesTab';
import { SkeletonGrid } from '../components/ui/page-states';
import { ErrorBoundary, ErrorState, invalidateAll } from '../data';
import { usePageTab } from '../hooks/usePageTab';
import { IMAGES_TAB_IDS, usePageUiStore } from '../stores/pageUiStore';
import {
  TAB_INSTAGRAM,
  TAB_CATALOG,
  TAB_MATCHES,
} from '../constants/strings';

const tabSuspenseFallback = <SkeletonGrid count={12} />;

export function ImagesPage() {
  const imagesTab = usePageUiStore((s) => s.imagesTab);
  const setImagesTab = usePageUiStore((s) => s.setImagesTab);
  const { activeTab, handleTabChange } = usePageTab({
    pagePath: '/images',
    tabIds: IMAGES_TAB_IDS,
    defaultTab: 'instagram',
    storedTab: imagesTab,
    setStoredTab: setImagesTab,
  });

  const tabs: Tab[] = [
    {
      id: 'instagram',
      label: TAB_INSTAGRAM,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['images.instagram']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <InstagramTab />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'catalog',
      label: TAB_CATALOG,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['images.catalog']);
                invalidateAll(['perspectives']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <CatalogTab />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'matches',
      label: TAB_MATCHES,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['matching.groups']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <MatchesTab />
          </Suspense>
        </ErrorBoundary>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">Images</h1>
        <p className="text-text-secondary">
          Browse Instagram photos, catalog images, and review matched pairs
        </p>
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  );
}
