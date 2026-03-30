import { Link } from 'react-router-dom';
import type { Job } from '../../services/api';
import {
  DESC_PAGE_BATCH_RUNNING,
  DESC_PAGE_FORCE,
  DESC_PAGE_MODEL_LABEL,
  MSG_LOADING,
  DESC_PAGE_FILTER_ALL,
  DESC_PAGE_FILTER_3M,
  DESC_PAGE_FILTER_6M,
  DESC_BATCH_JOB_STARTED,
  DESC_BATCH_VIEW_IN_JOBS,
  DESC_BATCH_FAILED_PREFIX,
} from '../../constants/strings';

type DateFilter = 'all' | '3months' | '6months';

const DATE_FILTERS: { value: DateFilter; label: string }[] = [
  { value: 'all', label: DESC_PAGE_FILTER_ALL },
  { value: '3months', label: DESC_PAGE_FILTER_3M },
  { value: '6months', label: DESC_PAGE_FILTER_6M },
];

interface ModelOption {
  name: string;
  default?: boolean;
}

export interface BatchActionPanelProps {
  availableModels: ModelOption[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  dateFilter: DateFilter;
  onDateFilterChange: (filter: DateFilter) => void;
  force: boolean;
  onForceChange: (force: boolean) => void;
  batchRunning: boolean;
  batchLabel: string;
  onBatchDescribe: () => void;
  batchJob: Job | null;
  onDismissJob: () => void;
  batchError: string | null;
  onDismissError: () => void;
}

export function BatchActionPanel({
  availableModels,
  selectedModel,
  onModelChange,
  dateFilter,
  onDateFilterChange,
  force,
  onForceChange,
  batchRunning,
  batchLabel,
  onBatchDescribe,
  batchJob,
  onDismissJob,
  batchError,
  onDismissError,
}: BatchActionPanelProps) {
  return (
    <>
      <div className="bg-white border rounded-lg p-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">{DESC_PAGE_MODEL_LABEL}</label>
          <select
            value={selectedModel}
            onChange={e => onModelChange(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
            aria-label="Vision model selector"
          >
            {availableModels.length === 0 ? (
              <option value="">{MSG_LOADING}</option>
            ) : (
              availableModels.map(m => (
                <option key={m.name} value={m.name}>
                  {m.name}{m.default ? ' (default)' : ''}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={dateFilter}
            onChange={e => onDateFilterChange(e.target.value as DateFilter)}
            className="border rounded px-2 py-1 text-sm"
            aria-label="Date range filter"
          >
            {DATE_FILTERS.map(f => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={force}
            onChange={e => onForceChange(e.target.checked)}
            className="rounded"
          />
          {DESC_PAGE_FORCE}
        </label>

        <button
          type="button"
          onClick={onBatchDescribe}
          disabled={batchRunning}
          className="ml-auto px-4 py-1.5 rounded text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {batchRunning ? DESC_PAGE_BATCH_RUNNING : batchLabel}
        </button>
      </div>

      {batchJob && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          <span>{DESC_BATCH_JOB_STARTED(batchJob.id.slice(0, 8))}</span>
          <Link to="/jobs" className="underline font-medium hover:text-green-900">{DESC_BATCH_VIEW_IN_JOBS}</Link>
          <button type="button" onClick={onDismissJob} className="ml-auto text-green-600 hover:text-green-800">&times;</button>
        </div>
      )}
      {batchError && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
          <span>{DESC_BATCH_FAILED_PREFIX} {batchError}</span>
          <button type="button" onClick={onDismissError} className="ml-auto text-red-600 hover:text-red-800">&times;</button>
        </div>
      )}
    </>
  );
}
