import { useState, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { useMatchOptions } from '../../stores/matchOptionsContext';
import { AdvancedOptions } from '../matching/AdvancedOptions';
import { ImagesAPI, JobsAPI, type CatalogSimilarityGroup } from '../../services/api';
import { ImageTile, fromCatalogListRow } from '../image-view';
import { invalidateAll, useQuery } from '../../data';
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

export interface MatchingTabProps {
  onJobEnqueued?: () => void;
}

export function MatchingTab(props: MatchingTabProps = {}) {
  const { onJobEnqueued } = props;
  const [dateFilter, setDateFilter] = useState<(typeof DATE_FILTERS)[number]['value']>('all');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isSimilarityStarting, setIsSimilarityStarting] = useState(false);
  const { options, updateOption, resetOptions, weightsError } = useMatchOptions();
  const catalogSimilarity = useQuery(
    ['catalog.similarity.groups', { limit: 12, offset: 0 }] as const,
    () => ImagesAPI.listCatalogSimilarityGroups({ limit: 12, offset: 0 }),
  );

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
        skip_undescribed: options.skipUndescribed,
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
  }, [dateFilter, options, weightsError, onJobEnqueued]);

  const startCatalogSimilarity = useCallback(async () => {
    setIsSimilarityStarting(true);
    try {
      await JobsAPI.create('batch_catalog_similarity', {
        min_similarity: 0.9,
        limit_per_seed: 8,
      });
      onJobEnqueued?.();
      invalidateAll(['catalog.similarity.groups']);
      alert('Catalog similarity job started! Check Job Queue tab to monitor progress.');
    } catch (error) {
      alert(`Failed to start job: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSimilarityStarting(false);
    }
  }, [onJobEnqueued]);

  const groups = catalogSimilarity.items ?? [];

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

      <Card padding="lg" className="mt-6">
        <CardHeader>
          <CardTitle>Find Similar Catalog Photos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">
              Runs a batch job over the existing visual index and saves reviewable catalog
              similarity groups. This does not modify the Lightroom catalog.
            </p>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={startCatalogSimilarity}
              disabled={isSimilarityStarting}
            >
              {isSimilarityStarting ? 'Starting Similarity Job...' : 'Find Similar Photos'}
            </Button>
            <CatalogSimilarityGroupsPreview groups={groups} total={catalogSimilarity.total} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CatalogSimilarityGroupsPreview({
  groups,
  total,
}: {
  groups: CatalogSimilarityGroup[]
  total?: number
}) {
  if (groups.length === 0) {
    return (
      <p className="rounded-base border border-border bg-surface p-4 text-sm text-text-secondary">
        No catalog similarity groups yet. Run Find Similar Photos after Embed Images completes.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Latest similarity groups</h3>
        <span className="text-xs text-text-secondary">{total ?? groups.length} groups</span>
      </div>
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.group_id} className="rounded-base border border-border bg-surface p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-text">
                Best match {Math.round(group.best_similarity * 100)}%
              </span>
              <span className="text-xs text-text-secondary">
                {group.candidate_count} candidate{group.candidate_count === 1 ? '' : 's'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <ImageTile
                image={fromCatalogListRow(group.seed)}
                variant="strip"
                primaryScoreSource="catalog"
                onClick={() => {}}
              />
              {group.candidates.slice(0, 3).map((candidate) => (
                <div key={candidate.key} className="space-y-1">
                  <ImageTile
                    image={fromCatalogListRow(candidate)}
                    variant="strip"
                    primaryScoreSource="catalog"
                    onClick={() => {}}
                  />
                  <p className="text-center text-xs text-text-secondary">
                    {Math.round((candidate.similarity ?? 0) * 100)}%
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
