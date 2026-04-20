import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import type { Job } from '../types/job';
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
  const jobsReqSeqRef = useRef(0);

  const fetchJobs = useCallback(async (offsetOverride: number | undefined, showSpinner: boolean) => {
    const nextOffset = offsetOverride ?? jobsOffset;
    const seq = ++jobsReqSeqRef.current;
    if (showSpinner) setJobsLoading(true);
    try {
      const response = await JobsAPI.list({ limit: PAGE_SIZE, offset: nextOffset });
      if (seq !== jobsReqSeqRef.current) return;
      setJobs(Array.isArray(response?.data) ? response.data : []);
      setJobsTotal(typeof response?.total === 'number' ? response.total : 0);
      // Always clear the spinner on a successful response, even for silent
      // refreshes. Previously the spinner was only cleared on the loud path,
      // so a silent refresh that landed after the initial load could strand
      // ``jobsLoading=true`` forever ("jobs are still loading i can't see them").
      setJobsLoading(false);
    } catch (err) {
      if (seq !== jobsReqSeqRef.current) return;
      console.error('Failed to load jobs:', err);
      // On error we still need to exit the loading state so the user sees
      // an empty table instead of a perpetual spinner.
      setJobsLoading(false);
    }
  }, [jobsOffset]);

  // User-triggered refresh (Refresh button) keeps the spinner for explicit feedback.
  const refreshJobs = useCallback((offsetOverride?: number) => fetchJobs(offsetOverride, true), [fetchJobs]);

  // Socket-driven refresh must not remount the table (causes flicker/full re-render).
  const refreshJobsSilently = useCallback(() => fetchJobs(undefined, false), [fetchJobs]);

  // Initial load + reload on pagination change. Uses the loud path so the
  // user sees a spinner while the very first response is in flight.
  useEffect(() => {
    void fetchJobs(jobsOffset, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobsOffset]);

  // Debounce silent refreshes so bursts of socket events coalesce into one fetch.
  const scheduleSilentRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = setTimeout(() => {
      void refreshJobsSilently();
    }, 400);
  }, [refreshJobsSilently]);

  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  const handleJobCreated = useCallback(
    (job: Job) => {
      // The new row may belong to a different page — defer to a silent refresh
      // rather than prepending blindly (which would drift pagination counts).
      if (jobsOffset === 0) {
        setJobs((prev) => {
          if (prev.some((j) => j.id === job.id)) return prev;
          const next = [job, ...prev];
          return next.length > PAGE_SIZE ? next.slice(0, PAGE_SIZE) : next;
        });
        setJobsTotal((prev) => prev + 1);
      } else {
        scheduleSilentRefresh();
      }
    },
    [jobsOffset, scheduleSilentRefresh],
  );

  const handleJobUpdated = useCallback((job: Job) => {
    // Patch the updated job in place. Status/progress flip live without the
    // whole table unmounting — no spinner, no flicker.
    setJobs((prev) => {
      let changed = false;
      const next = prev.map((j) => {
        if (j.id !== job.id) return j;
        changed = true;
        return job;
      });
      return changed ? next : prev;
    });
  }, []);

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
    { id: 'analyze', label: TAB_ANALYZE, content: <AnalyzeTab /> },
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

      <JobsHealthBanner />

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
