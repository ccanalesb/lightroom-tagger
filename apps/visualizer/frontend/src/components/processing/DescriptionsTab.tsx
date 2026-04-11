import { useState, useCallback, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { WorkerSlider } from '../matching/WorkerSlider';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
import { useMatchOptions } from '../../stores/matchOptionsContext';
import { JobsAPI, ProvidersAPI } from '../../services/api';
import { ADVANCED_OPTIONS_TITLE } from '../../constants/strings';

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

export function DescriptionsTab() {
  const { options, updateOption } = useMatchOptions();
  const [imageType, setImageType] = useState<ImageType>('both');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [batchMinRating, setBatchMinRating] = useState<number | null>(null);
  const [force, setForce] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [descProviderId, setDescProviderId] = useState<string | null>(null);
  const [descProviderModel, setDescProviderModel] = useState<string | null>(null);

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

  const startDescriptions = useCallback(async () => {
    setIsStarting(true);
    try {
      const metadata: Record<string, unknown> = {
        image_type: imageType,
        date_filter: dateFilter,
        force,
        max_workers: options.maxWorkers,
      };

      if (batchMinRating !== null) metadata.min_rating = batchMinRating;
      if (descProviderId) metadata.provider_id = descProviderId;
      if (descProviderModel) metadata.provider_model = descProviderModel;

      await JobsAPI.create('batch_describe', metadata);
      alert('Description generation job started! Check Job Queue tab to monitor progress.');
    } catch (error) {
      alert(`Failed to start job: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsStarting(false);
    }
  }, [imageType, dateFilter, batchMinRating, force, options, descProviderId, descProviderModel]);

  return (
    <div>
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Generate Image Descriptions</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-6">
            <p className="text-sm text-text-secondary">
              AI-generated descriptions improve matching accuracy by providing semantic context.
            </p>

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
                id="force-regenerate"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
                className="w-4 h-4 rounded border-border text-accent focus:ring-accent focus:ring-offset-0"
              />
              <label htmlFor="force-regenerate" className="text-sm text-text cursor-pointer">
                Force regenerate existing descriptions
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
              </div>
            )}

            <div className="pt-4">
              <Button variant="primary" size="lg" fullWidth onClick={startDescriptions} disabled={isStarting}>
                {isStarting ? 'Starting Job...' : 'Generate Descriptions'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
