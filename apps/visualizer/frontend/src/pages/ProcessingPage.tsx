import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '../components/ui/Tabs';
import { MatchingTab } from '../components/processing/MatchingTab';
import { DescriptionsTab } from '../components/processing/DescriptionsTab';
import { CatalogCacheTab } from '../components/processing/CatalogCacheTab';
import { JobQueueTab } from '../components/processing/JobQueueTab';
import { ProvidersTab } from '../components/processing/ProvidersTab';
import { SettingsTab } from '../components/processing/SettingsTab';
import {
  TAB_VISION_MATCHING,
  TAB_DESCRIPTIONS,
  TAB_CATALOG_CACHE,
  TAB_JOB_QUEUE,
  TAB_PROVIDERS,
  TAB_SETTINGS,
  NAV_PROCESSING,
} from '../constants/strings';

const PROCESSING_TAB_IDS = ['matching', 'descriptions', 'cache', 'jobs', 'providers', 'settings'] as const;
type ProcessingTabId = (typeof PROCESSING_TAB_IDS)[number];

function tabIdFromSearch(search: string): ProcessingTabId {
  const tab = new URLSearchParams(search).get('tab');
  if (tab && PROCESSING_TAB_IDS.includes(tab as ProcessingTabId)) {
    return tab as ProcessingTabId;
  }
  return 'matching';
}

export function ProcessingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = useMemo(() => tabIdFromSearch(location.search), [location.search]);

  const handleTabChange = (id: string) => {
    if (!PROCESSING_TAB_IDS.includes(id as ProcessingTabId)) return;
    const next = id as ProcessingTabId;
    navigate(
      { pathname: '/processing', search: next === 'matching' ? '' : `?tab=${next}` },
      { replace: true },
    );
  };

  const tabs: Tab[] = [
    { id: 'matching', label: TAB_VISION_MATCHING, content: <MatchingTab /> },
    { id: 'descriptions', label: TAB_DESCRIPTIONS, content: <DescriptionsTab /> },
    { id: 'cache', label: TAB_CATALOG_CACHE, content: <CatalogCacheTab /> },
    { id: 'jobs', label: TAB_JOB_QUEUE, content: <JobQueueTab /> },
    { id: 'providers', label: TAB_PROVIDERS, content: <ProvidersTab /> },
    { id: 'settings', label: TAB_SETTINGS, content: <SettingsTab /> },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">{NAV_PROCESSING}</h1>
        <p className="text-text-secondary">
          Vision matching, descriptions, catalog cache management, and job monitoring
        </p>
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  );
}
