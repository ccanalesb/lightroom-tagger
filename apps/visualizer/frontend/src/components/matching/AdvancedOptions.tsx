import { RangeSlider } from './RangeSlider';
import { WeightSlider } from './WeightSlider';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
import {
  ADVANCED_OPTIONS_TITLE,
  ADVANCED_THRESHOLD_LABEL,
  ADVANCED_THRESHOLD_MIN,
  ADVANCED_THRESHOLD_MAX,
  ADVANCED_THRESHOLD_DESCRIPTION,
  ADVANCED_WEIGHTS_TITLE,
  ADVANCED_WEIGHTS_TOTAL,
  ADVANCED_WEIGHT_PHASH,
  ADVANCED_WEIGHT_DESC,
  ADVANCED_WEIGHT_VISION,
  ADVANCED_RESET_DEFAULTS,
} from '../../constants/strings';

interface AdvancedOptionsProps {
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
  onReset: () => void;
}

export function AdvancedOptions({
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
  onReset,
}: AdvancedOptionsProps) {
  const totalWeight = phashWeight + descWeight + visionWeight;
  const weightsValid = Math.abs(totalWeight - 1.0) < 0.001;

  return (
    <div className="border-t pt-4">
      <button
        onClick={onToggle}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {isOpen ? '▼' : '▶'} {ADVANCED_OPTIONS_TITLE}
      </button>

      {isOpen && (
        <div className="mt-4 space-y-4 bg-white p-4 rounded border">
          <ProviderModelSelect
            providerId={providerId}
            modelId={providerModel}
            onChange={onProviderChange}
          />

          <RangeSlider
            label={ADVANCED_THRESHOLD_LABEL}
            valueLabel={`: ${threshold.toFixed(2)}`}
            min={0.5}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={onThresholdChange}
            minLabel={ADVANCED_THRESHOLD_MIN}
            maxLabel={ADVANCED_THRESHOLD_MAX}
            description={ADVANCED_THRESHOLD_DESCRIPTION}
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {ADVANCED_WEIGHTS_TITLE}
            </label>

            {weightsError && (
              <div className="text-sm text-red-600 mb-2 p-2 bg-red-50 rounded">
                {weightsError}
              </div>
            )}

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

            <div className="mt-2 text-sm">
              <span className="text-gray-600">{ADVANCED_WEIGHTS_TOTAL}: </span>
              <span
                className={
                  weightsValid
                    ? 'text-green-600 font-medium'
                    : 'text-red-600 font-medium'
                }
              >
                {(totalWeight * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="pt-2 border-t">
            <button
              onClick={onReset}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              {ADVANCED_RESET_DEFAULTS}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
