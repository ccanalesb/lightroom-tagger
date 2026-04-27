import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input/Input';
import { useMatchOptions } from '../../stores/matchOptionsContext';
import { AdvancedOptions } from '../matching/AdvancedOptions';
import { JobsAPI } from '../../services/api';
import {
  ADVANCED_DATE_FILTER,
  ADVANCED_DATE_ALL,
  ADVANCED_DATE_3MONTHS,
  ADVANCED_DATE_6MONTHS,
  ADVANCED_DATE_12MONTHS,
  ADVANCED_DATE_YEAR_2026,
  ADVANCED_DATE_YEAR_2025,
  ADVANCED_DATE_YEAR_2024,
  ADVANCED_DATE_YEAR_2023,
  ADVANCED_FIX_WEIGHTS,
  MATCHING_CLIP_TOP_K_LABEL,
  MATCHING_CLIP_TOP_K_HELPER,
  MATCHING_CLIP_TOP_K_ERROR,
  MATCHING_CATALOG_CACHE_POINTER,
  PROCESSING_CATALOG_CACHE_ROUTE,
} from '../../constants/strings';

const DATE_FILTERS = [
  { value: 'all', label: ADVANCED_DATE_ALL },
  { value: '3months', label: ADVANCED_DATE_3MONTHS },
  { value: '6months', label: ADVANCED_DATE_6MONTHS },
  { value: '12months', label: ADVANCED_DATE_12MONTHS },
  { value: '2026', label: ADVANCED_DATE_YEAR_2026 },
  { value: '2025', label: ADVANCED_DATE_YEAR_2025 },
  { value: '2024', label: ADVANCED_DATE_YEAR_2024 },
  { value: '2023', label: ADVANCED_DATE_YEAR_2023 },
] as const;

export interface MatchingTabProps {
  onJobEnqueued?: () => void;
}

export function MatchingTab(props: MatchingTabProps = {}) {
  const { onJobEnqueued } = props;
  const [dateFilter, setDateFilter] = useState<(typeof DATE_FILTERS)[number]['value']>('all');
  const [clipTopKDraft, setClipTopKDraft] = useState('50');
  const [clipTopKError, setClipTopKError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const { options, updateOption, resetOptions, weightsError } = useMatchOptions();

  const clampClipTopKOnBlur = useCallback(() => {
    setClipTopKDraft((prev) => {
      let n = parseInt(prev, 10);
      if (prev === '' || Number.isNaN(n)) {
        return '50';
      }
      n = Math.min(500, Math.max(1, n));
      return String(n);
    });
    setClipTopKError(null);
  }, []);

  const startMatching = useCallback(async () => {
    if (weightsError) {
      alert(ADVANCED_FIX_WEIGHTS);
      return;
    }

    const clipTopK = parseInt(clipTopKDraft, 10);
    if (!Number.isFinite(clipTopK) || clipTopK < 1 || clipTopK > 500) {
      setClipTopKError(MATCHING_CLIP_TOP_K_ERROR);
      return;
    }

    setIsStarting(true);
    try {
      const metadata: Record<string, unknown> = {
        threshold: options.threshold,
        weights: {
          phash: options.phashWeight,
          description: options.descWeight,
          vision: options.visionWeight,
        },
        max_workers: options.maxWorkers,
        skip_undescribed: options.skipUndescribed,
        clip_top_k: clipTopK,
        ...(options.providerId ? { provider_id: options.providerId } : {}),
        ...(options.providerModel ? { provider_model: options.providerModel } : {}),
      };

      if (dateFilter === '3months') metadata.last_months = 3;
      else if (dateFilter === '6months') metadata.last_months = 6;
      else if (dateFilter === '12months') metadata.last_months = 12;
      else if (dateFilter === '2026') metadata.year = '2026';
      else if (dateFilter === '2025') metadata.year = '2025';
      else if (dateFilter === '2024') metadata.year = '2024';
      else if (dateFilter === '2023') metadata.year = '2023';

      await JobsAPI.create('vision_match', metadata);
      onJobEnqueued?.();
      alert('Vision matching job started! Check Job Queue tab to monitor progress.');
    } catch (error) {
      alert(`Failed to start job: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsStarting(false);
    }
  }, [clipTopKDraft, dateFilter, options, weightsError, onJobEnqueued]);

  return (
    <div>
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Start Vision Matching Job</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-text mb-2">
                {ADVANCED_DATE_FILTER}
              </label>
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value as (typeof DATE_FILTERS)[number]['value'])}
                className="w-full px-3 py-2 rounded-base border border-border bg-bg text-text focus:outline-none focus:ring-2 focus:ring-accent hover:border-border-strong transition-all"
              >
                {DATE_FILTERS.map((filter) => (
                  <option key={filter.value} value={filter.value}>
                    {filter.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Input
                id="matching-clip-top-k"
                label={MATCHING_CLIP_TOP_K_LABEL}
                type="number"
                inputMode="numeric"
                min={1}
                max={500}
                step={1}
                value={clipTopKDraft}
                onChange={(e) => {
                  setClipTopKError(null);
                  setClipTopKDraft(e.target.value.replace(/\D/g, ''));
                }}
                onBlur={clampClipTopKOnBlur}
                error={clipTopKError ?? undefined}
                fullWidth
              />
              <p className="mt-1 text-sm text-text-secondary">{MATCHING_CLIP_TOP_K_HELPER}</p>
            </div>

            <p className="text-sm text-text-secondary">
              <Link
                to={PROCESSING_CATALOG_CACHE_ROUTE}
                className="font-semibold text-accent hover:underline focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 rounded-sm"
              >
                {MATCHING_CATALOG_CACHE_POINTER}
              </Link>
            </p>

            <AdvancedOptions
              isOpen={showAdvanced}
              onToggle={() => setShowAdvanced(!showAdvanced)}
              {...options}
              onProviderChange={(providerId, modelId) => {
                updateOption('providerId', providerId);
                updateOption('providerModel', modelId);
              }}
              onThresholdChange={(v) => updateOption('threshold', v)}
              onPhashWeightChange={(v) => updateOption('phashWeight', v)}
              onDescWeightChange={(v) => updateOption('descWeight', v)}
              onVisionWeightChange={(v) => updateOption('visionWeight', v)}
              maxWorkers={options.maxWorkers}
              onMaxWorkersChange={(v) => updateOption('maxWorkers', v)}
              onSkipUndescribedChange={(v) => updateOption('skipUndescribed', v)}
              weightsError={weightsError}
              onReset={resetOptions}
            />

            <div className="pt-4">
              <Button variant="primary" size="lg" fullWidth onClick={startMatching} disabled={isStarting || !!weightsError}>
                {isStarting ? 'Starting Job...' : 'Start Vision Matching'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
