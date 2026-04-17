import { useState, useCallback, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { WorkerSlider } from '../matching/WorkerSlider';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
import { useMatchOptions } from '../../stores/matchOptionsContext';
import { JobsAPI, PerspectivesAPI, ProvidersAPI } from '../../services/api';
import {
  ADVANCED_OPTIONS_TITLE,
  ANALYZE_ADVANCED_DESCRIBE_ONLY,
  ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE,
  ANALYZE_ADVANCED_SCORE_ONLY,
  ANALYZE_CARD_SUBTITLE,
  ANALYZE_CARD_TITLE,
  ANALYZE_DESCRIBE_JOB_STARTED,
  ANALYZE_FORCE_DESCRIBE_LABEL,
  ANALYZE_FORCE_SCORE_LABEL,
  ANALYZE_JOB_FAILED_PREFIX,
  ANALYZE_JOB_STARTED,
  ANALYZE_PRIMARY_BUTTON,
  ANALYZE_PRIMARY_BUTTON_STARTING,
  ANALYZE_SCORE_JOB_STARTED,
} from '../../constants/strings';

type ImageType = 'both' | 'instagram' | 'catalog';
type DateFilter = 'all' | '3months' | '6months' | '12months';

const IMAGE_TYPE_OPTIONS: { value: ImageType; label: string }[] = [
  { value: 'both', label: 'Instagram + Catalog' },
  { value: 'instagram', label: 'Instagram Only' },
  { value: 'catalog', label: 'Catalog Only' },
];

const DATE_FILTER_OPTIONS: { value: DateFilter; label: string }[] = [
  { value: 'all', label: 'All time' },
  { value: '3months', label: 'Last 3 months' },
  { value: '6months', label: 'Last 6 months' },
  { value: '12months', label: 'Last 12 months' },
];

export function AnalyzeTab() {
  const { options, updateOption } = useMatchOptions();
  const [imageType, setImageType] = useState<ImageType>('both');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [batchMinRating, setBatchMinRating] = useState<number | null>(null);
  const [forceDescribe, setForceDescribe] = useState(false);
  const [forceScore, setForceScore] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStartingAnalyze, setIsStartingAnalyze] = useState(false);
  const [isStartingDescribe, setIsStartingDescribe] = useState(false);
  const [isStartingScore, setIsStartingScore] = useState(false);
  const [descProviderId, setDescProviderId] = useState<string | null>(null);
  const [descProviderModel, setDescProviderModel] = useState<string | null>(null);
  const [activePerspectiveRows, setActivePerspectiveRows] = useState<
    { slug: string; display_name: string }[]
  >([]);
  const [selectedPerspectiveSlugs, setSelectedPerspectiveSlugs] = useState<string[]>([]);

  useEffect(() => {
    PerspectivesAPI.list({ active_only: true })
      .then((rows) => {
        const sorted = [...rows].sort((a, b) => a.slug.localeCompare(b.slug));
        setActivePerspectiveRows(sorted.map((r) => ({ slug: r.slug, display_name: r.display_name })));
        setSelectedPerspectiveSlugs(sorted.map((r) => r.slug));
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    ProvidersAPI.getDefaults()
      .then(defaults => {
        if (defaults.description?.provider) {
          setDescProviderId(defaults.description.provider);
          setDescProviderModel(defaults.description.model ?? null);
        }
      })
      .catch(console.error);
  }, []);

  const buildSharedBaseMetadata = useCallback((): Record<string, unknown> => {
    const metadata: Record<string, unknown> = {
      image_type: imageType,
      date_filter: dateFilter,
      max_workers: options.maxWorkers,
    };
    if (batchMinRating !== null) metadata.min_rating = batchMinRating;
    if (descProviderId) metadata.provider_id = descProviderId;
    if (descProviderModel) metadata.provider_model = descProviderModel;
    metadata.perspective_slugs = [...selectedPerspectiveSlugs];
    return metadata;
  }, [
    imageType,
    dateFilter,
    batchMinRating,
    options.maxWorkers,
    descProviderId,
    descProviderModel,
    selectedPerspectiveSlugs,
  ]);

  const buildBatchJobMetadata = useCallback((): Record<string, unknown> => {
    return {
      ...buildSharedBaseMetadata(),
      force_describe: forceDescribe,
      force_score: forceScore,
    };
  }, [buildSharedBaseMetadata, forceDescribe, forceScore]);

  const startAnalyze = useCallback(async () => {
    setIsStartingAnalyze(true);
    try {
      await JobsAPI.create('batch_analyze', buildBatchJobMetadata());
      alert(ANALYZE_JOB_STARTED);
    } catch (error) {
      alert(
        `${ANALYZE_JOB_FAILED_PREFIX} ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
      );
    } finally {
      setIsStartingAnalyze(false);
    }
  }, [buildBatchJobMetadata]);

  const startDescriptionsOnly = useCallback(async () => {
    setIsStartingDescribe(true);
    try {
      const base = buildSharedBaseMetadata();
      await JobsAPI.create('batch_describe', { ...base, 'force': forceDescribe });
      alert(ANALYZE_DESCRIBE_JOB_STARTED);
    } catch (error) {
      alert(
        `${ANALYZE_JOB_FAILED_PREFIX} ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
      );
    } finally {
      setIsStartingDescribe(false);
    }
  }, [buildSharedBaseMetadata, forceDescribe]);

  const startScoringOnly = useCallback(async () => {
    setIsStartingScore(true);
    try {
      const base = buildSharedBaseMetadata();
      await JobsAPI.create('batch_score', { ...base, 'force': forceScore });
      alert(ANALYZE_SCORE_JOB_STARTED);
    } catch (error) {
      alert(
        `${ANALYZE_JOB_FAILED_PREFIX} ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
      );
    } finally {
      setIsStartingScore(false);
    }
  }, [buildSharedBaseMetadata, forceScore]);

  return (
    <div>
      <Card padding="lg">
        <CardHeader>
          <CardTitle>{ANALYZE_CARD_TITLE}</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-6">
            <p className="text-sm text-text-secondary">{ANALYZE_CARD_SUBTITLE}</p>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                Image Source
              </label>
              <select
                value={imageType}
                onChange={(e) => setImageType(e.target.value as ImageType)}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
              >
                {IMAGE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                Date Range
              </label>
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value as DateFilter)}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
              >
                {DATE_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <span className="block text-sm font-medium text-text mb-2">Critique perspectives</span>
              <p className="text-xs text-text-secondary mb-2">
                Uncheck to limit which active lenses run. None selected uses all active perspectives.
              </p>
              <div className="flex flex-col gap-2 max-h-40 overflow-y-auto border border-border rounded-base p-3 bg-bg">
                {activePerspectiveRows.length === 0 ? (
                  <span className="text-sm text-text-secondary">Loading perspectives…</span>
                ) : (
                  activePerspectiveRows.map((p) => (
                    <label
                      key={p.slug}
                      className="flex items-center gap-2 text-sm text-text cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedPerspectiveSlugs.includes(p.slug)}
                        onChange={() => {
                          setSelectedPerspectiveSlugs((prev) =>
                            prev.includes(p.slug)
                              ? prev.filter((s) => s !== p.slug)
                              : [...prev, p.slug].sort((a, b) => a.localeCompare(b)),
                          );
                        }}
                        className="w-4 h-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
                      />
                      <span>
                        {p.display_name} <span className="text-text-secondary">({p.slug})</span>
                      </span>
                    </label>
                  ))
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-2">
                Minimum rating (catalog)
              </label>
              <select
                value={batchMinRating === null ? '' : String(batchMinRating)}
                onChange={(e) => {
                  const v = e.target.value;
                  setBatchMinRating(v === '' ? null : Number(v));
                }}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
              >
                <option value="">Any</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}+ stars
                  </option>
                ))}
              </select>
              <p className="mt-1.5 text-xs text-text-secondary">
                Applies to catalog (and both); Instagram-only batches ignore this filter.
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="force-regenerate-describe"
                checked={forceDescribe}
                onChange={(e) => setForceDescribe(e.target.checked)}
                className="w-4 h-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
              />
              <label
                htmlFor="force-regenerate-describe"
                className="text-sm text-text cursor-pointer"
              >
                {ANALYZE_FORCE_DESCRIBE_LABEL}
              </label>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="force-regenerate-score"
                checked={forceScore}
                onChange={(e) => setForceScore(e.target.checked)}
                className="w-4 h-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
              />
              <label
                htmlFor="force-regenerate-score"
                className="text-sm text-text cursor-pointer"
              >
                {ANALYZE_FORCE_SCORE_LABEL}
              </label>
            </div>

            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center space-x-2 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span>{ADVANCED_OPTIONS_TITLE}</span>
              </button>
            </div>

            {showAdvanced && (
              <div className="pt-4 border-t border-border space-y-4">
                <ProviderModelSelect
                  providerId={descProviderId}
                  modelId={descProviderModel}
                  onChange={(providerId, modelId) => {
                    setDescProviderId(providerId);
                    setDescProviderModel(modelId);
                  }}
                />
                <WorkerSlider value={options.maxWorkers} onChange={(v) => updateOption('maxWorkers', v)} />

                <div className="pt-4 border-t border-border space-y-3">
                  <h3 className="text-sm font-semibold text-text">
                    {ANALYZE_ADVANCED_RUN_SEPARATELY_TITLE}
                  </h3>
                  <Button
                    variant="secondary"
                    size="md"
                    fullWidth
                    onClick={startDescriptionsOnly}
                    disabled={isStartingDescribe}
                  >
                    {isStartingDescribe
                      ? ANALYZE_PRIMARY_BUTTON_STARTING
                      : ANALYZE_ADVANCED_DESCRIBE_ONLY}
                  </Button>
                  <Button
                    variant="secondary"
                    size="md"
                    fullWidth
                    onClick={startScoringOnly}
                    disabled={isStartingScore}
                  >
                    {isStartingScore
                      ? ANALYZE_PRIMARY_BUTTON_STARTING
                      : ANALYZE_ADVANCED_SCORE_ONLY}
                  </Button>
                </div>
              </div>
            )}

            <div className="pt-4 space-y-3">
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={startAnalyze}
                disabled={isStartingAnalyze}
              >
                {isStartingAnalyze ? ANALYZE_PRIMARY_BUTTON_STARTING : ANALYZE_PRIMARY_BUTTON}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
