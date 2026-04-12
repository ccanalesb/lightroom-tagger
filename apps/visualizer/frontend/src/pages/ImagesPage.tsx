import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '../components/ui/Tabs';
import { InstagramTab } from '../components/images/InstagramTab';
import { CatalogTab } from '../components/images/CatalogTab';
import { MatchesTab } from '../components/images/MatchesTab';
import {
  IMAGES_OPEN_POSTING_ANALYTICS,
  TAB_INSTAGRAM,
  TAB_CATALOG,
  TAB_MATCHES,
} from '../constants/strings';

const IMAGES_TAB_IDS = ['instagram', 'catalog', 'matches'] as const;
type ImagesTabId = (typeof IMAGES_TAB_IDS)[number];

function tabIdFromSearch(search: string): ImagesTabId {
  const tab = new URLSearchParams(search).get('tab');
  if (tab && IMAGES_TAB_IDS.includes(tab as ImagesTabId)) {
    return tab as ImagesTabId;
  }
  return 'instagram';
}

export function ImagesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = useMemo(() => tabIdFromSearch(location.search), [location.search]);
  const [catalogPostedFilter, setCatalogPostedFilter] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    if (activeTab !== 'catalog') {
      setCatalogPostedFilter(undefined);
    }
  }, [activeTab]);

  const handleTabChange = (id: string) => {
    if (!IMAGES_TAB_IDS.includes(id as ImagesTabId)) return;
    const next = id as ImagesTabId;
    navigate(
      { pathname: '/images', search: next === 'instagram' ? '' : `?tab=${next}` },
      { replace: true },
    );
  };

  const tabs: Tab[] = [
    { id: 'instagram', label: TAB_INSTAGRAM, content: <InstagramTab /> },
    {
      id: 'catalog',
      label: TAB_CATALOG,
      content: (
        <div className="space-y-3">
          {catalogPostedFilter === false ? (
            <p className="rounded-base border border-border bg-surface px-3 py-2 text-sm text-text-secondary">
              <Link
                to="/analytics"
                className="font-medium text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent rounded-sm"
              >
                {IMAGES_OPEN_POSTING_ANALYTICS}
              </Link>
              <span className="text-text-tertiary"> — </span>
              Gap list with date, rating, and month filters lives on the Analytics page.
            </p>
          ) : null}
          <CatalogTab onPostedFilterChange={setCatalogPostedFilter} />
        </div>
      ),
    },
    { id: 'matches', label: TAB_MATCHES, content: <MatchesTab /> },
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
