import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MatchingAPI, JobsAPI, SystemAPI, Match, Job } from '../services/api';
import { MatchDetailModal, AdvancedOptions, MatchCard } from '../components';
import { useSocketStore } from '../stores/socketStore';
import {
  MSG_LOADING,
  MSG_ERROR_PREFIX,
  MSG_NO_MATCHES,
  MATCHING_RESULTS,
  ACTION_RUN_MATCHING,
  ADVANCED_DATE_ALL,
  ADVANCED_DATE_3MONTHS,
  ADVANCED_DATE_6MONTHS,
  ADVANCED_DATE_YEAR_2026,
  ADVANCED_FORCE_DESCRIPTIONS,
  ADVANCED_START,
  ADVANCED_STARTING,
  ADVANCED_DATE_FILTER,
  MATCHING_IN_PROGRESS,
  MATCHING_WAITING,
  MATCHING_PERCENT_COMPLETE,
  MATCHING_PROCESSING,
  MATCHING_VIEW_DETAILS,
  MATCHING_COMPLETED,
  MATCHING_COMPLETED_MATCHES,
  MATCHING_FAILED,
  MATCHING_FAILED_UNKNOWN,
  MATCHING_DISMISS,
  CACHE_TITLE,
  CACHE_PREPARE_BUTTON,
  CACHE_PREPARING,
  CACHE_STATUS_LOADING,
  CACHE_STATUS_CACHED,
  CACHE_STATUS_OF,
  CACHE_STATUS_IMAGES,
  CACHE_SIZE_LABEL,
  CACHE_REFRESH_BUTTON,
  CACHE_JOB_RUNNING,
  CACHE_JOB_COMPLETED,
  CACHE_WARNING_NOT_READY,
} from '../constants/strings';

type CacheStatus = {
  total_images: number;
  cached_images: number;
  missing: number;
  cache_size_mb: number;
  cache_dir: string;
};

const DATE_FILTERS = [
  { value: 'all', label: ADVANCED_DATE_ALL },
  { value: '3months', label: ADVANCED_DATE_3MONTHS },
  { value: '6months', label: ADVANCED_DATE_6MONTHS },
  { value: '2026', label: ADVANCED_DATE_YEAR_2026 },
] as const;

const DEFAULT_OPTIONS = {
  selectedModel: '',
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
};

export function MatchingPage() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTrigger, setShowTrigger] = useState(false);
  const [dateFilter, setDateFilter] = useState<(typeof DATE_FILTERS)[number]['value']>('all');
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  // Advanced options
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [availableModels, setAvailableModels] = useState<{ name: string; default: boolean }[]>([]);
  const [options, setOptions] = useState({ ...DEFAULT_OPTIONS });
  const [weightsError, setWeightsError] = useState<string | null>(null);

  // Cache status
  const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null);
  const [isPreparingCache, setIsPreparingCache] = useState(false);
  const [cacheJob, setCacheJob] = useState<Job | null>(null);
  const [forceDescriptions, setForceDescriptions] = useState(false);

  const navigate = useNavigate();
  const { socket, connected } = useSocketStore();

  const canStart = useMemo(
    () => !isStarting && activeJob?.status !== 'running' && !weightsError,
    [isStarting, activeJob?.status, weightsError]
  );

  const isCacheReady = useMemo(() => {
    if (!cacheStatus) return false;
    return cacheStatus.cached_images === cacheStatus.total_images && cacheStatus.total_images > 0;
  }, [cacheStatus]);

  // Fetch cache status
  const fetchCacheStatus = useCallback(async () => {
    try {
      const status = await SystemAPI.cacheStatus();
      setCacheStatus(status);
    } catch (err) {
      console.error('Failed to fetch cache status:', err);
    }
  }, []);

  // Fetch data
  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        const [matchesData, jobsData] = await Promise.all([
          MatchingAPI.list(100),
          JobsAPI.getActive(),
        ]);

        if (!mounted) return;

        setMatches(matchesData.matches);
        setTotal(matchesData.total);

        const runningJob = jobsData.find(
          (job: Job) => job.type === 'vision_match' && ['pending', 'running'].includes(job.status)
        );
        if (runningJob) setActiveJob(runningJob);

        // Check for running prepare_catalog job
        const runningCacheJob = jobsData.find(
          (job: Job) => job.type === 'prepare_catalog' && ['pending', 'running'].includes(job.status)
        );
        if (runningCacheJob) {
          setCacheJob(runningCacheJob);
          setIsPreparingCache(true);
        }
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();
    fetchCacheStatus();

    // Fetch models
    SystemAPI.visionModels()
      .then((data) => {
        if (!mounted) return;
        setAvailableModels(data.models);
        const defaultModel = data.models.find((m) => m.default) ?? data.models[0];
        if (defaultModel) setOptions((prev) => ({ ...prev, selectedModel: defaultModel.name }));
      })
      .catch(console.error);

    return () => { mounted = false; };
  }, [fetchCacheStatus]);

  // Validate weights
  useEffect(() => {
    const total = options.phashWeight + options.descWeight + options.visionWeight;
    setWeightsError(Math.abs(total - 1.0) > 0.001 ? `Weights must sum to 100% (currently ${(total * 100).toFixed(0)}%)` : null);
  }, [options.phashWeight, options.descWeight, options.visionWeight]);

  // WebSocket updates
  useEffect(() => {
    if (!socket || !connected) return;

    const handleJobCreated = (job: Job) => {
      if (job.type === 'vision_match') {
        setActiveJob(job);
        setIsStarting(false);
        setShowTrigger(false);
      } else if (job.type === 'prepare_catalog') {
        setCacheJob(job);
        setIsPreparingCache(true);
      }
    };

    const handleJobUpdated = (job: Job) => {
      if (job.id === activeJob?.id) {
        setActiveJob(job);
        if (job.status === 'completed') {
          setTimeout(() => {
            MatchingAPI.list(100).then((data) => {
              setMatches(data.matches);
              setTotal(data.total);
            });
          }, 1000);
        }
      }
      if (job.id === cacheJob?.id) {
        setCacheJob(job);
        if (job.status === 'completed') {
          setIsPreparingCache(false);
          fetchCacheStatus();
        }
      }
    };

    socket.on('job_created', handleJobCreated);
    socket.on('job_updated', handleJobUpdated);

    return () => {
      socket.off('job_created', handleJobCreated);
      socket.off('job_updated', handleJobUpdated);
    };
  }, [socket, connected, activeJob?.id, cacheJob?.id, fetchCacheStatus]);

  const startMatching = useCallback(async () => {
    if (weightsError) {
      alert('Please fix weight configuration before starting');
      return;
    }

    setIsStarting(true);

    const metadata: Record<string, unknown> = {
      vision_model: options.selectedModel,
      threshold: options.threshold,
      weights: {
        phash: options.phashWeight,
        description: options.descWeight,
        vision: options.visionWeight,
      },
    };

    if (forceDescriptions) metadata.force_descriptions = true;

    if (dateFilter === '3months') metadata.last_months = 3;
    else if (dateFilter === '6months') metadata.last_months = 6;
    else if (dateFilter === '2026') metadata.year = '2026';

    try {
      const job = await JobsAPI.create('vision_match', metadata);
      setActiveJob(job);
      setIsStarting(false);
      setShowTrigger(false);
    } catch (err) {
      setIsStarting(false);
      alert(`Failed to start matching: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [weightsError, options, dateFilter, forceDescriptions]);

  const startCachePreparation = useCallback(async () => {
    setIsPreparingCache(true);
    try {
      const job = await JobsAPI.create('prepare_catalog', {});
      setCacheJob(job);
    } catch (err) {
      setIsPreparingCache(false);
      alert(`Failed to start cache preparation: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, []);

  const resetOptions = useCallback(() => setOptions({ ...DEFAULT_OPTIONS }), []);

  const updateOption = useCallback(<K extends keyof typeof options>(key: K, value: (typeof options)[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Cache status display
  const renderCacheStatus = () => {
    if (isPreparingCache || !cacheStatus) {
      return (
        <div className="text-xs text-gray-500">{CACHE_STATUS_LOADING}</div>
      );
    }

    const { cached_images, total_images, cache_size_mb } = cacheStatus;
    const percentage = total_images > 0 ? Math.round((cached_images / total_images) * 100) : 0;

    return (
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isCacheReady ? 'bg-green-500' : 'bg-yellow-500'}`} />
        <span className="text-xs text-gray-600">
          {cached_images} {CACHE_STATUS_CACHED} {CACHE_STATUS_OF} {total_images} {CACHE_STATUS_IMAGES} ({percentage}%)
        </span>
        <span className="text-xs text-gray-400">|</span>
        <span className="text-xs text-gray-600">
          {CACHE_SIZE_LABEL}: {cache_size_mb.toFixed(1)}MB
        </span>
        <button
          onClick={fetchCacheStatus}
          disabled={isPreparingCache}
          className="text-xs text-blue-600 hover:text-blue-800 underline ml-2"
        >
          {CACHE_REFRESH_BUTTON}
        </button>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{MSG_LOADING}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">
          {MSG_ERROR_PREFIX} {error}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cache Status Panel */}
      <div className="bg-gray-50 p-3 rounded-lg border">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-700">{CACHE_TITLE}</span>
            {renderCacheStatus()}
          </div>
          <button
            onClick={startCachePreparation}
            disabled={isPreparingCache || cacheJob?.status === 'running'}
            className="px-3 py-1.5 bg-purple-600 text-white text-xs rounded hover:bg-purple-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPreparingCache ? CACHE_PREPARING : CACHE_PREPARE_BUTTON}
          </button>
        </div>
        {cacheJob?.status === 'running' && (
          <div className="mt-2 text-xs text-purple-700">
            {CACHE_JOB_RUNNING} {cacheJob.progress ? `${cacheJob.progress}%` : ''}
          </div>
        )}
        {cacheJob?.status === 'completed' && (
          <div className="mt-2 text-xs text-green-700">
            {CACHE_JOB_COMPLETED} {cacheJob.result?.cached || 0} images cached
          </div>
        )}
        {!isCacheReady && cacheStatus && cacheStatus.total_images > 0 && (
          <div className="mt-2 text-xs text-yellow-700">
            {CACHE_WARNING_NOT_READY}
          </div>
        )}
      </div>

      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">{MATCHING_RESULTS}</h2>
        <div className="flex items-center gap-4">
          <p className="text-sm text-gray-500">{total} matches</p>
          <button
            onClick={() => setShowTrigger(!showTrigger)}
            disabled={!canStart}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStarting ? ADVANCED_STARTING : ACTION_RUN_MATCHING}
          </button>
        </div>
      </div>

      {/* Job Status Panels */}
      {activeJob && activeJob.status !== 'completed' && <JobStatusPanel job={activeJob} onView={() => navigate('/jobs')} />}
      {activeJob?.status === 'completed' && (
        <CompletedPanel matches={activeJob.result?.matched || 0} onDismiss={() => setActiveJob(null)} />
      )}
      {activeJob?.status === 'failed' && (
        <FailedPanel error={activeJob.error} onDismiss={() => setActiveJob(null)} />
      )}

      {/* Trigger Panel */}
      {showTrigger && !activeJob && (
        <div className="bg-gray-50 p-4 rounded-lg border space-y-4">
          <div className="flex items-center gap-4 flex-wrap">
            <label className="text-sm font-medium text-gray-700">{ADVANCED_DATE_FILTER}</label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as (typeof DATE_FILTERS)[number]['value'])}
              className="px-3 py-2 border rounded text-sm"
            >
              {DATE_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
            <button
              onClick={startMatching}
              disabled={!!weightsError}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm font-medium disabled:opacity-50"
            >
              {isStarting ? ADVANCED_STARTING : ADVANCED_START}
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={forceDescriptions}
              onChange={(e) => setForceDescriptions(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            {ADVANCED_FORCE_DESCRIPTIONS}
          </label>

          <AdvancedOptions
            isOpen={showAdvanced}
            onToggle={() => setShowAdvanced(!showAdvanced)}
            availableModels={availableModels}
            {...options}
            onModelChange={(v) => updateOption('selectedModel', v)}
            onThresholdChange={(v) => updateOption('threshold', v)}
            onPhashWeightChange={(v) => updateOption('phashWeight', v)}
            onDescWeightChange={(v) => updateOption('descWeight', v)}
            onVisionWeightChange={(v) => updateOption('visionWeight', v)}
            weightsError={weightsError}
            onReset={resetOptions}
          />
        </div>
      )}

      {/* Matches Grid */}
      {matches.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{MSG_NO_MATCHES}</p>
          <p className="text-sm text-gray-400 mt-2">Click "Run Matching" above to start the matching process.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {matches.map((match, idx) => (
            <MatchCard key={`${match.instagram_key}-${idx}`} match={match} onClick={() => setSelectedMatch(match)} />
          ))}
        </div>
      )}

      {/* Modal */}
      {selectedMatch && <MatchDetailModal match={selectedMatch} onClose={() => setSelectedMatch(null)} />}
    </div>
  );
}

// Status Panel Components
function JobStatusPanel({ job, onView }: { job: Job; onView: () => void }) {
  return (
    <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
          <div>
            <p className="font-medium text-blue-900">{MATCHING_IN_PROGRESS}</p>
            <p className="text-sm text-blue-700">
              {job.status === 'pending'
                ? MATCHING_WAITING
                : job.progress
                ? `${job.progress}${MATCHING_PERCENT_COMPLETE}`
                : MATCHING_PROCESSING}
            </p>
          </div>
        </div>
        <button onClick={onView} className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          {MATCHING_VIEW_DETAILS}
        </button>
      </div>
    </div>
  );
}

function CompletedPanel({ matches, onDismiss }: { matches: number; onDismiss: () => void }) {
  return (
    <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <div>
            <p className="font-medium text-green-900">{MATCHING_COMPLETED}</p>
            <p className="text-sm text-green-700">
              {matches} {MATCHING_COMPLETED_MATCHES}
            </p>
          </div>
        </div>
        <button onClick={onDismiss} className="text-green-700 hover:text-green-900">
          {MATCHING_DISMISS}
        </button>
      </div>
    </div>
  );
}

function FailedPanel({ error, onDismiss }: { error?: string | null; onDismiss: () => void }) {
  return (
    <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          <div>
            <p className="font-medium text-red-900">{MATCHING_FAILED}</p>
            <p className="text-sm text-red-700">{error || MATCHING_FAILED_UNKNOWN}</p>
          </div>
        </div>
        <button onClick={onDismiss} className="text-red-700 hover:text-red-900">
          {MATCHING_DISMISS}
        </button>
      </div>
    </div>
  );
}
