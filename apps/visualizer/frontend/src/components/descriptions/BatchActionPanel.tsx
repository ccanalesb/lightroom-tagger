import { Link } from 'react-router-dom';
import type { Job } from '../../services/api';
import {
  ADVANCED_DATE_12MONTHS,
  ADVANCED_DATE_18MONTHS,
  ADVANCED_DATE_1MONTH,
  ADVANCED_DATE_24MONTHS,
  ADVANCED_DATE_2MONTHS,
  ADVANCED_DATE_3MONTHS,
  ADVANCED_DATE_6MONTHS,
  ADVANCED_DATE_9MONTHS,
  ADVANCED_DATE_ALL,
  ADVANCED_DATE_YEAR_2023,
  ADVANCED_DATE_YEAR_2024,
  ADVANCED_DATE_YEAR_2025,
  ADVANCED_DATE_YEAR_2026,
  DESC_PAGE_BATCH_RUNNING,
  DESC_PAGE_FORCE,
  DESC_BATCH_JOB_STARTED,
  DESC_BATCH_VIEW_IN_JOBS,
  DESC_BATCH_FAILED_PREFIX,
} from '../../constants/strings';

// ``DateFilter`` mirrors the union in AnalyzeTab so downstream call sites can
// share the same type + ``buildDateMetadata`` translator. This panel isn't
// mounted in the current UI but is exported for future reuse — keeping the
// enum aligned now avoids a second migration later.
type DateFilter =
  | 'all'
  | '1months'
  | '2months'
  | '3months'
  | '6months'
  | '9months'
  | '12months'
  | '18months'
  | '24months'
  | '2026'
  | '2025'
  | '2024'
  | '2023';

const DATE_FILTERS: { value: DateFilter; label: string }[] = [
  { value: 'all', label: ADVANCED_DATE_ALL },
  { value: '1months', label: ADVANCED_DATE_1MONTH },
  { value: '2months', label: ADVANCED_DATE_2MONTHS },
  { value: '3months', label: ADVANCED_DATE_3MONTHS },
  { value: '6months', label: ADVANCED_DATE_6MONTHS },
  { value: '9months', label: ADVANCED_DATE_9MONTHS },
  { value: '12months', label: ADVANCED_DATE_12MONTHS },
  { value: '18months', label: ADVANCED_DATE_18MONTHS },
  { value: '24months', label: ADVANCED_DATE_24MONTHS },
  { value: '2026', label: ADVANCED_DATE_YEAR_2026 },
  { value: '2025', label: ADVANCED_DATE_YEAR_2025 },
  { value: '2024', label: ADVANCED_DATE_YEAR_2024 },
  { value: '2023', label: ADVANCED_DATE_YEAR_2023 },
];

export interface BatchActionPanelProps {
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
          <Link to="/processing?tab=jobs" className="underline font-medium hover:text-green-900">{DESC_BATCH_VIEW_IN_JOBS}</Link>
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
