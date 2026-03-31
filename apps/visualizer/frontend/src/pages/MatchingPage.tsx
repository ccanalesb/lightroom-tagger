import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { JobsAPI, SystemAPI, Match, MatchGroup, Job } from '../services/api';
import { MatchDetailModal } from '../components/matching/match-detail-modal';
import { AdvancedOptions } from '../components/matching/AdvancedOptions';
import { MatchCard } from '../components/matching/MatchCard';
import { JobStatusPanel, CompletedPanel, FailedPanel } from '../components/matching/job-status-panels';
import { useJobSocket } from '../hooks/useJobSocket';
import { useMatchGroups } from '../hooks/useMatchGroups';
import { useMatchOptions } from '../stores/matchOptionsContext';
import { PageLoading, PageError } from '../components/ui/page-states';
import {
  MSG_NO_MATCHES,
  MATCHING_RESULTS,
  MATCHING_RUN_PROMPT,
  ACTION_RUN_MATCHING,
  ADVANCED_DATE_ALL,
  ADVANCED_DATE_3MONTHS,
  ADVANCED_DATE_6MONTHS,
  ADVANCED_DATE_YEAR_2026,
  ADVANCED_FORCE_DESCRIPTIONS,
  ADVANCED_FORCE_REPROCESS,
  ADVANCED_START,
  ADVANCED_STARTING,
  ADVANCED_DATE_FILTER,
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

export function MatchingPage() {
  const { matchGroups, total, fetchGroups, handleValidationChange, handleRejected } = useMatchGroups();
  const [selectedGroup, setSelectedGroup] = useState<MatchGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTrigger, setShowTrigger] = useState(false);
  const [dateFilter, setDateFilter] = useState<(typeof DATE_FILTERS)[number]['value']>('all');
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const { options, updateOption, resetOptions, availableModels, weightsError } = useMatchOptions();

  const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null);
  const [isPreparingCache, setIsPreparingCache] = useState(false);
  const [cacheJob, setCacheJob] = useState<Job | null>(null);
  const [forceDescriptions, setForceDescriptions] = useState(false);
  const [forceReprocess, setForceReprocess] = useState(false);

  const navigate = useNavigate();

  const canStart = useMemo(
    () => !isStarting && activeJob?.status !== 'running' && !weightsError,
    [isStarting, activeJob?.status, weightsError]
  );

  const isCacheReady = useMemo(() => {
    if (!cacheStatus) return false;
    return cacheStatus.cached_images === cacheStatus.total_images && cacheStatus.total_images > 0;
  }, [cacheStatus]);

  const fetchCacheStatus = useCallback(async () => {
    try {
      const status = await SystemAPI.cacheStatus();
      setCacheStatus(status);
    } catch (err) {
      console.error('Failed to fetch cache status:', err);
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        const [, jobsData] = await Promise.all([fetchGroups(100), JobsAPI.getActive()]);

        if (!mounted) return;

        const runningJob = jobsData.find(
          (job: Job) => job.type === 'vision_match' && ['pending', 'running'].includes(job.status)
        );
        if (runningJob) setActiveJob(runningJob);

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

    return () => { mounted = false; };
  }, [fetchCacheStatus, fetchGroups]);

  const handleJobCreated = useCallback((job: Job) => {
    if (job.type === 'vision_match') {
      setActiveJob(job);
      setIsStarting(false);
      setShowTrigger(false);
    } else if (job.type === 'prepare_catalog') {
      setCacheJob(job);
      setIsPreparingCache(true);
    }
  }, []);

  const handleJobUpdated = useCallback((job: Job) => {
    if (job.id === activeJob?.id) {
      setActiveJob(job);
      if (job.status === 'completed') {
        setTimeout(() => {
          fetchGroups(100);
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
  }, [activeJob?.id, cacheJob?.id, fetchCacheStatus, fetchGroups]);

  useJobSocket({
    onJobCreated: handleJobCreated,
    onJobUpdated: handleJobUpdated,
  });

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

    if (options.providerId) {
      metadata.provider_id = options.providerId;
      if (options.providerModel) metadata.provider_model = options.providerModel;
    }

    if (forceDescriptions) metadata.force_descriptions = true;
    if (forceReprocess) metadata.force_reprocess = true;

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
  }, [weightsError, options, dateFilter, forceDescriptions, forceReprocess]);

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

  if (loading) return <PageLoading />;
  if (error) return <PageError message={error} />;

  return (
    <div className="space-y-6">
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

      {activeJob && activeJob.status !== 'completed' && <JobStatusPanel job={activeJob} onView={() => navigate('/jobs')} />}
      {activeJob?.status === 'completed' && (
        <CompletedPanel matches={activeJob.result?.matched || 0} onDismiss={() => setActiveJob(null)} />
      )}
      {activeJob?.status === 'failed' && (
        <FailedPanel error={activeJob.error} onDismiss={() => setActiveJob(null)} />
      )}

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

          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={forceReprocess}
                onChange={(e) => setForceReprocess(e.target.checked)}
                className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
              />
              {ADVANCED_FORCE_REPROCESS}
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={forceDescriptions}
                onChange={(e) => setForceDescriptions(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              {ADVANCED_FORCE_DESCRIPTIONS}
            </label>
          </div>

          <AdvancedOptions
            isOpen={showAdvanced}
            onToggle={() => setShowAdvanced(!showAdvanced)}
            availableModels={availableModels}
            {...options}
            onProviderChange={(providerId, modelId) => {
              updateOption('providerId', providerId);
              updateOption('providerModel', modelId);
            }}
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

      {matchGroups.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{MSG_NO_MATCHES}</p>
          <p className="text-sm text-gray-400 mt-2">{MATCHING_RUN_PROMPT}</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {matchGroups.map((group) => (
            <MatchCard
              key={group.instagram_key}
              group={group}
              onClick={(candidate) => {
                setSelectedMatch(candidate);
                setSelectedGroup(group);
              }}
            />
          ))}
        </div>
      )}

      {selectedMatch && (
        <MatchDetailModal
          match={selectedMatch}
          group={() =>
            matchGroups.find((group) => group.instagram_key === selectedMatch.instagram_key) ??
            selectedGroup ??
            undefined
          }
          onClose={() => {
            setSelectedMatch(null);
            setSelectedGroup(null);
          }}
          onValidationChange={(match, validated) => {
            handleValidationChange(match, validated);
            setSelectedMatch((prev) =>
              prev ? { ...prev, validated_at: validated ? new Date().toISOString() : undefined } : null
            );
          }}
          onRejected={(match) => {
            handleRejected(match);
            setSelectedMatch(null);
            setSelectedGroup(null);
          }}
          onCandidateChange={(candidate) => setSelectedMatch(candidate)}
        />
      )}
    </div>
  );
}
