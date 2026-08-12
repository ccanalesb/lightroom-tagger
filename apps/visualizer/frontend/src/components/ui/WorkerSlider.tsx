import { RangeSlider } from './RangeSlider';
import {
  ADVANCED_WORKERS_LABEL,
  ADVANCED_WORKERS_MIN,
  ADVANCED_WORKERS_MAX,
  ADVANCED_WORKERS_DESCRIPTION,
} from '../../constants/strings';

interface WorkerSliderProps {
  value: number;
  onChange: (value: number) => void;
}

export function WorkerSlider({ value, onChange }: WorkerSliderProps) {
  return (
    <RangeSlider
      label={ADVANCED_WORKERS_LABEL}
      valueLabel={`: ${value}`}
      min={1}
      max={4}
      step={1}
      value={value}
      onChange={onChange}
      minLabel={ADVANCED_WORKERS_MIN}
      maxLabel={ADVANCED_WORKERS_MAX}
      description={ADVANCED_WORKERS_DESCRIPTION}
    />
  );
}
