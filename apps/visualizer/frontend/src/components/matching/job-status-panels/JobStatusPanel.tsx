import type { Job } from '../../../services/api';
import {
  MATCHING_IN_PROGRESS,
  MATCHING_WAITING,
  MATCHING_PERCENT_COMPLETE,
  MATCHING_PROCESSING,
  MATCHING_VIEW_DETAILS,
} from '../../../constants/strings';

export function JobStatusPanel({ job, onView }: { job: Job; onView: () => void }) {
  return (
    <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
          <div>
            <p className="font-medium text-blue-900">{MATCHING_IN_PROGRESS}</p>
            <p className="text-sm text-blue-700">
              {job.status === 'pending'
                ? MATCHING_WAITING
                : job.progress
                ? `${job.progress}${MATCHING_PERCENT_COMPLETE}`
                : MATCHING_PROCESSING}
            </p>
          </div>
        </div>
        <button onClick={onView} className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
          {MATCHING_VIEW_DETAILS}
        </button>
      </div>
    </div>
  );
}
