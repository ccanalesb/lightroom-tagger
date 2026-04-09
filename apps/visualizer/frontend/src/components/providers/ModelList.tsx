import type { ProviderModel } from '../../services/api';
import {
  PROVIDER_COL_ACTIONS,
  PROVIDER_COL_MODEL,
  PROVIDER_COL_SOURCE,
  PROVIDER_COL_VISION,
  PROVIDER_REMOVE_MODEL,
  PROVIDER_SOURCE_CONFIG,
  PROVIDER_SOURCE_DISCOVERED,
  PROVIDER_SOURCE_USER,
} from '../../constants/strings';
import { Button } from '../ui/Button';

const SOURCE_LABELS: Record<string, string> = {
  config: PROVIDER_SOURCE_CONFIG,
  discovered: PROVIDER_SOURCE_DISCOVERED,
  user: PROVIDER_SOURCE_USER,
};

interface ModelListProps {
  models: ProviderModel[];
  onRemove: (modelId: string) => void;
}

export function ModelList({ models, onRemove }: ModelListProps) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-text-secondary text-xs uppercase tracking-wider">
          <th className="pb-1">{PROVIDER_COL_MODEL}</th>
          <th className="pb-1">{PROVIDER_COL_VISION}</th>
          <th className="pb-1">{PROVIDER_COL_SOURCE}</th>
          <th className="pb-1 w-10 text-right font-normal">{PROVIDER_COL_ACTIONS}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {models.map(model => (
          <tr key={model.id}>
            <td className="py-1.5 font-mono text-xs text-text">{model.name}</td>
            <td className="py-1.5">
              {model.vision ? (
                <span className="text-success">✓</span>
              ) : (
                <span className="text-text-tertiary">—</span>
              )}
            </td>
            <td className="py-1.5 text-xs text-text-secondary">
              {SOURCE_LABELS[model.source] ?? model.source}
            </td>
            <td className="py-1.5 text-right">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={PROVIDER_REMOVE_MODEL}
                className="!px-1 !py-0 min-w-0 text-text-tertiary hover:text-error"
                onClick={() => onRemove(model.id)}
              >
                ×
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
