import { RangeSlider } from './RangeSlider';

interface WeightSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
}

export function WeightSlider({ label, value, onChange }: WeightSliderProps) {
  return (
    <div>
      <label className="flex justify-between text-sm">
        <span>{label}</span>
        <span>{(value * 100).toFixed(0)}%</span>
      </label>
      <RangeSlider
        label=""
        min={0}
        max={1}
        step={0.05}
        value={value}
        onChange={onChange}
        className="mt-1"
      />
    </div>
  );
}
