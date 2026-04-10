import { RangeSlider } from '../matching/RangeSlider';
import { WeightSlider } from '../matching/WeightSlider';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
import {
  ADVANCED_OPTIONS_TITLE,
  ADVANCED_WEIGHT_PHASH,
  ADVANCED_WEIGHT_DESC,
  ADVANCED_WEIGHT_VISION,
} from '../../constants/strings';

interface MatchAdvancedOptionsProps {
  isOpen: boolean;
  onToggle: () => void;
  providerId: string | null;
  providerModel: string | null;
  onProviderChange: (providerId: string | null, modelId: string | null) => void;
  threshold: number;
  onThresholdChange: (value: number) => void;
  phashWeight: number;
  onPhashWeightChange: (value: number) => void;
  descWeight: number;
  onDescWeightChange: (value: number) => void;
  visionWeight: number;
  onVisionWeightChange: (value: number) => void;
  weightsError: string | null;
}

export function MatchAdvancedOptions({
  isOpen,
  onToggle,
  providerId,
  providerModel,
  onProviderChange,
  threshold,
  onThresholdChange,
  phashWeight,
  onPhashWeightChange,
  descWeight,
  onDescWeightChange,
  visionWeight,
  onVisionWeightChange,
  weightsError,
}: MatchAdvancedOptionsProps) {
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="text-sm font-medium text-text-secondary hover:text-text transition-colors"
      >
        {isOpen ? '▼' : '▶'} {ADVANCED_OPTIONS_TITLE}
      </button>

      {isOpen && (
        <div className="space-y-4 pt-2 border-t border-border mt-2">
          <ProviderModelSelect
            providerId={providerId}
            modelId={providerModel}
            onChange={onProviderChange}
          />

          <RangeSlider
            label="Threshold"
            valueLabel={`: ${threshold.toFixed(2)}`}
            min={0.5}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={onThresholdChange}
          />

          <div className="space-y-3">
            <WeightSlider
              label={ADVANCED_WEIGHT_PHASH}
              value={phashWeight}
              onChange={onPhashWeightChange}
            />
            <WeightSlider
              label={ADVANCED_WEIGHT_DESC}
              value={descWeight}
              onChange={onDescWeightChange}
            />
            <WeightSlider
              label={ADVANCED_WEIGHT_VISION}
              value={visionWeight}
              onChange={onVisionWeightChange}
            />
          </div>

          {weightsError && (
            <p className="text-xs text-error">{weightsError}</p>
          )}
        </div>
      )}
    </div>
  );
}
