import type { Job } from '../../services/api';
import type { SingleMatchState } from '../../hooks/useSingleMatch';
import { Button } from '../ui/Button';
import {
  MODAL_MATCH_THIS_PHOTO,
  MODAL_MATCH_RUNNING,
  MODAL_MATCH_RESULT_FOUND,
  MODAL_MATCH_RESULT_NONE,
} from '../../constants/strings';

interface MatchStatusDisplayProps {
  state: SingleMatchState;
  job: Job | null;
  result: { matched: number; score?: number } | null;
  error: string | null;
  disabled: boolean;
  onStart: () => void;
  onReset: () => void;
}

export function MatchStatusDisplay({
  state,
  job,
  result,
  error,
  disabled,
  onStart,
  onReset,
}: MatchStatusDisplayProps) {
  if (state === 'idle') {
    return (
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={onStart}
        disabled={disabled}
      >
        {MODAL_MATCH_THIS_PHOTO}
      </Button>
    );
  }

  if (state === 'running') {
    return (
      <div className="flex items-center gap-2 py-3 px-4 bg-surface rounded-base text-sm text-accent border border-accent">
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
            fill="none"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <span className="font-medium">
          {MODAL_MATCH_RUNNING}
          {job && ` ${job.progress}%`}
        </span>
      </div>
    );
  }

  if (state === 'done') {
    if (error || job?.status === 'failed') {
      return (
        <div className="py-3 px-4 rounded-base text-sm bg-surface text-error border border-error">
          <p className="font-medium">
            Match failed: {error || job?.error || 'Unknown error'}
          </p>
          <button
            type="button"
            onClick={onReset}
            className="text-xs font-medium text-error hover:underline mt-1"
          >
            Try Again
          </button>
        </div>
      );
    }

    if (result) {
      return (
        <div
          className={`py-3 px-4 rounded-base text-sm border ${
            result.matched > 0
              ? 'bg-surface text-success border-success'
              : 'bg-surface text-text-secondary border-border'
          }`}
        >
          <p className="font-medium">
            {result.matched > 0 ? MODAL_MATCH_RESULT_FOUND : MODAL_MATCH_RESULT_NONE}
            {result.score != null && ` (score: ${result.score.toFixed(2)})`}
          </p>
          <div className="flex gap-3 mt-2">
            {result.matched > 0 && (
              <a href="/images?tab=matches" className="text-xs font-medium text-accent hover:underline">
                View Results
              </a>
            )}
            <button
              type="button"
              onClick={onReset}
              className="text-xs font-medium text-text-secondary hover:text-text hover:underline"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
  }

  return null;
}
