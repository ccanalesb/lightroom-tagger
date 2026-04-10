import { useState, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
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

export function MatchingTab() {
  const [dateFilter, setDateFilter] = useState<(typeof DATE_FILTERS)[number]['value']>('all');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const { options, updateOption, resetOptions, weightsError } = useMatchOptions();

  const startMatching = useCallback(async () => {
    if (weightsError) {
      alert('Please fix weight configuration before starting');
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
      alert('Vision matching job started! Check Job Queue tab to monitor progress.');
    } catch (error) {
      alert(`Failed to start job: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsStarting(false);
    }
  }, [dateFilter, options, weightsError]);

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
