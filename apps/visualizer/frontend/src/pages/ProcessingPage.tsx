import { Suspense, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '../components/ui/Tabs';
import { MatchingTab } from '../components/processing/MatchingTab';
import { AnalyzeTab } from '../components/processing/AnalyzeTab';
import { CatalogCacheTab } from '../components/processing/CatalogCacheTab';
import { JobQueueTab } from '../components/processing/JobQueueTab';
import { JobsHealthBanner } from '../components/processing/JobsHealthBanner';
import { ProvidersTab } from '../components/processing/ProvidersTab';
import { SettingsTab } from '../components/processing/SettingsTab';
import { PerspectivesTab } from '../components/processing/PerspectivesTab';
import { Button } from '../components/ui/Button';
import { useJobSocket } from '../hooks/useJobSocket';
import { JobsAPI } from '../services/api';
import { ErrorBoundary, ErrorState, invalidateAll, useQuery } from '../data';
import {
  TAB_VISION_MATCHING,
  TAB_ANALYZE,
  TAB_PERSPECTIVES,
  TAB_CATALOG_CACHE,
  TAB_JOB_QUEUE,
  TAB_PROVIDERS,
  TAB_SETTINGS,
  NAV_PROCESSING,
} from '../constants/strings';

const PAGE_SIZE = 50;

const PROCESSING_TAB_IDS = [
  'matching',
  'analyze',
  'perspectives',
  'cache',
  'jobs',
  'providers',
  'settings',
] as const;
type ProcessingTabId = (typeof PROCESSING_TAB_IDS)[number];

function tabIdFromSearch(search: string): ProcessingTabId {
  const tab = new URLSearchParams(search).get('tab');
  if (tab && PROCESSING_TAB_IDS.includes(tab as ProcessingTabId)) {
    return tab as ProcessingTabId;
  }
  return 'matching';
}

const JOBS_RECOVERED_BANNER =
  'Some jobs were automatically resumed after the last server restart. Check the job queue for progress.';

const tabSuspenseFallback = (
  <div className="rounded-card border border-border bg-surface p-8 text-center text-sm text-text-secondary">
    Loading…
  </div>
);

function JobQueueTabWithData({
  connected,
  jobListRevision,
  refreshJobList,
}: {
  connected: boolean;
  jobListRevision: number;
  refreshJobList: () => void;
}) {
  const [jobsOffset, setJobsOffset] = useState(0);
  const listResponse = useQuery(
    ['jobs.list', { limit: PAGE_SIZE, offset: jobsOffset, rev: jobListRevision }] as const,
    () => JobsAPI.list({ limit: PAGE_SIZE, offset: jobsOffset }),
  );

  const jobs = Array.isArray(listResponse?.data) ? listResponse.data : [];
  const jobsTotal = typeof listResponse?.total === 'number' ? listResponse.total : 0;

  return (
    <JobQueueTab
      jobs={jobs}
      connected={connected}
      onRefreshJobs={refreshJobList}
      onInvalidateJobList={refreshJobList}
      pagination={{
        offset: jobsOffset,
        limit: PAGE_SIZE,
        total: jobsTotal,
      }}
      onOffsetChange={setJobsOffset}
    />
  );
}

export function ProcessingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = useMemo(() => tabIdFromSearch(location.search), [location.search]);

  const [jobsRecoveredBanner, setJobsRecoveredBanner] = useState<string | null>(null);

  const { connected, jobListRevision, healthRevision, refreshJobList } = useJobSocket({
    onJobsRecovered: () => setJobsRecoveredBanner(JOBS_RECOVERED_BANNER),
  });

  const handleTabChange = (id: string) => {
    if (!PROCESSING_TAB_IDS.includes(id as ProcessingTabId)) return;
    const next = id as ProcessingTabId;
    navigate(
      { pathname: '/processing', search: next === 'matching' ? '' : `?tab=${next}` },
      { replace: true },
    );
  };

  const tabs: Tab[] = [
    {
      id: 'matching',
      label: TAB_VISION_MATCHING,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState error={error} reset={reset} title="Could not load matching tab" />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <MatchingTab onJobEnqueued={refreshJobList} />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'analyze',
      label: TAB_ANALYZE,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState error={error} reset={reset} title="Could not load analyze tab" />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <AnalyzeTab onJobEnqueued={refreshJobList} />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'perspectives',
      label: TAB_PERSPECTIVES,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['perspectives']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <PerspectivesTab />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'cache',
      label: TAB_CATALOG_CACHE,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['catalog.cache.stats']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <CatalogCacheTab onJobEnqueued={refreshJobList} />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'jobs',
      label: TAB_JOB_QUEUE,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['jobs.list']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <JobQueueTabWithData
              connected={connected}
              jobListRevision={jobListRevision}
              refreshJobList={refreshJobList}
            />
          </Suspense>
        </ErrorBoundary>
      ),
    },
    {
      id: 'providers',
      label: TAB_PROVIDERS,
      content: (
        <ErrorBoundary
          fallback={({ error, reset }) => (
            <ErrorState
              error={error}
              reset={() => {
                invalidateAll(['providers.list']);
                reset();
              }}
            />
          )}
        >
          <Suspense fallback={tabSuspenseFallback}>
            <ProvidersTab />
          </Suspense>
        </ErrorBoundary>
      ),
    },
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

      <JobsHealthBanner cacheRevision={healthRevision} />

      {jobsRecoveredBanner ? (
        <div
          className="mb-4 flex items-start justify-between gap-4 rounded-card border border-border bg-surface p-4 shadow-card"
          role="status"
        >
          <p className="text-sm text-text">{jobsRecoveredBanner}</p>
          <Button
            variant="secondary"
            size="sm"
            type="button"
            onClick={() => setJobsRecoveredBanner(null)}
          >
            Dismiss
          </Button>
        </div>
      ) : null}

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  );
}
