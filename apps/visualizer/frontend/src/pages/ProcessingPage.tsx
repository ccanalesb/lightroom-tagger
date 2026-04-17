import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '../components/ui/Tabs';
import { MatchingTab } from '../components/processing/MatchingTab';
import { DescriptionsTab } from '../components/processing/DescriptionsTab';
import { CatalogCacheTab } from '../components/processing/CatalogCacheTab';
import { JobQueueTab } from '../components/processing/JobQueueTab';
import { ProvidersTab } from '../components/processing/ProvidersTab';
import { SettingsTab } from '../components/processing/SettingsTab';
import { PerspectivesTab } from '../components/processing/PerspectivesTab';
import { Button } from '../components/ui/Button';
import { useJobSocket } from '../hooks/useJobSocket';
import { JobsAPI } from '../services/api';
import type { Job } from '../types/job';
import {
  TAB_VISION_MATCHING,
  TAB_DESCRIPTIONS,
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
  'descriptions',
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

export function ProcessingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = useMemo(() => tabIdFromSearch(location.search), [location.search]);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsOffset, setJobsOffset] = useState(0);
  const [jobsRecoveredBanner, setJobsRecoveredBanner] = useState<string | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshJobs = useCallback(async (offsetOverride?: number) => {
    const nextOffset = offsetOverride ?? jobsOffset;
    setJobsLoading(true);
    try {
      const response = await JobsAPI.list({ limit: PAGE_SIZE, offset: nextOffset });
      setJobs(Array.isArray(response?.data) ? response.data : []);
      setJobsTotal(typeof response?.total === 'number' ? response.total : 0);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setJobsLoading(false);
    }
  }, [jobsOffset]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const response = await JobsAPI.list({ limit: PAGE_SIZE, offset: jobsOffset });
        if (!mounted) return;
        setJobs(Array.isArray(response?.data) ? response.data : []);
        setJobsTotal(typeof response?.total === 'number' ? response.total : 0);
      } catch (err) {
        console.error('Failed to load jobs:', err);
      } finally {
        if (mounted) setJobsLoading(false);
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, [jobsOffset]);

  const scheduleRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = setTimeout(() => {
      void refreshJobs();
    }, 400);
  }, [refreshJobs]);

  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  const handleJobCreated = useCallback(() => {
    scheduleRefresh();
  }, [scheduleRefresh]);

  const handleJobUpdated = useCallback(() => {
    scheduleRefresh();
  }, [scheduleRefresh]);

  const { connected } = useJobSocket({
    onJobCreated: handleJobCreated,
    onJobUpdated: handleJobUpdated,
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
    { id: 'matching', label: TAB_VISION_MATCHING, content: <MatchingTab /> },
    { id: 'descriptions', label: TAB_DESCRIPTIONS, content: <DescriptionsTab /> },
    { id: 'perspectives', label: TAB_PERSPECTIVES, content: <PerspectivesTab /> },
    { id: 'cache', label: TAB_CATALOG_CACHE, content: <CatalogCacheTab /> },
    {
      id: 'jobs',
      label: TAB_JOB_QUEUE,
      content: (
        <JobQueueTab
          jobs={jobs}
          setJobs={setJobs}
          jobsLoading={jobsLoading}
          connected={connected}
          onRefreshJobs={() => refreshJobs()}
          pagination={{
            offset: jobsOffset,
            limit: PAGE_SIZE,
            total: jobsTotal,
          }}
          onOffsetChange={setJobsOffset}
        />
      ),
    },
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
