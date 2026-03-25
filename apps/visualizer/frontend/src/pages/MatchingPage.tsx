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
} from '../constants/strings';

const DATE_FILTERS = [
  { value: 'all', label: ADVANCED_DATE_ALL },
  { value: '3months', label: ADVANCED_DATE_3MONTHS },
  { value: '6months', label: ADVANCED_DATE_6MONTHS },
  { value: '2026', label: ADVANCED_DATE_YEAR_2026 },
] as const;

const DEFAULT_OPTIONS = {
  selectedModel: 'gemma3:27b',
  threshold: 0.7,
  phashWeight: 0.4,
  descWeight: 0.3,
  visionWeight: 0.3,
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

  const navigate = useNavigate();
  const { socket, connected } = useSocketStore();

  const canStart = useMemo(
    () => !isStarting && activeJob?.status !== 'running' && !weightsError,
    [isStarting, activeJob?.status, weightsError]
  );

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
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();

    // Fetch models
    SystemAPI.visionModels()
      .then((data) => {
        if (!mounted) return;
        setAvailableModels(data.models);
        const defaultModel = data.models.find((m) => m.default);
        if (defaultModel) setOptions((prev) => ({ ...prev, selectedModel: defaultModel.name }));
      })
      .catch(console.error);

    return () => {
      mounted = false;
    };
  }, []);

  // Validate weights
  useEffect(() => {
    const total = options.phashWeight + options.descWeight + options.visionWeight;
    setWeightsError(Math.abs(total - 1.0) > 0.001 ? `Weights must sum to 100% (currently ${(total * 100).toFixed(0)}%)` : null);
  }, [options.phashWeight, options.descWeight, options.visionWeight]);

  // WebSocket updates
  useEffect(() => {
    if (!socket || !connected) return;

    const handleJobCreated = (job: Job) => {
      if (job.type !== 'vision_match') return;
      setActiveJob(job);
      setIsStarting(false);
      setShowTrigger(false);
    };

    const handleJobUpdated = (job: Job) => {
      if (job.id !== activeJob?.id) return;
      setActiveJob(job);

      if (job.status !== 'completed') return;
      setTimeout(() => {
        MatchingAPI.list(100).then((data) => {
          setMatches(data.matches);
          setTotal(data.total);
        });
      }, 1000);
    };

    socket.on('job_created', handleJobCreated);
    socket.on('job_updated', handleJobUpdated);

    return () => {
      socket.off('job_created', handleJobCreated);
      socket.off('job_updated', handleJobUpdated);
    };
  }, [socket, connected, activeJob?.id]);

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
  }, [weightsError, options, dateFilter]);

  const resetOptions = useCallback(() => setOptions({ ...DEFAULT_OPTIONS }), []);

  const updateOption = useCallback(<K extends keyof typeof options>(key: K, value: (typeof options)[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

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
