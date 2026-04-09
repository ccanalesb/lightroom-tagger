import { useState } from 'react';
import { AdvancedOptions } from '../matching/AdvancedOptions';
import {
  MODAL_MATCH_RESULT_FOUND,
  MODAL_MATCH_RESULT_NONE,
  MODAL_MATCH_RETRY,
  MODAL_MATCH_RUNNING,
  MODAL_MATCH_THIS_PHOTO,
  MODAL_MATCH_VIEW_RESULTS,
  MODAL_ALREADY_MATCHED,
  ADVANCED_FORCE_REPROCESS,
  MODAL_VIEW_ON_INSTAGRAM,
  INSTAGRAM_VIA,
  MSG_UNKNOWN_ERROR,
  MODAL_MATCH_JOB_FAILED_PREFIX,
} from '../../constants/strings';
import { useSingleMatch } from '../../hooks/useSingleMatch';
import type { InstagramImage } from '../../services/api';
import { useMatchOptions } from '../../stores/matchOptionsContext';

interface SingleMatchSectionProps {
  image: InstagramImage;
}

export function SingleMatchSection({ image }: SingleMatchSectionProps) {
  const { options: matchOptions, updateOption, resetOptions, weightsError } =
    useMatchOptions();
  const {
    matchState,
    matchJob,
    matchResult,
    matchError,
    startSingleMatch,
    resetMatch,
  } = useSingleMatch(image.key);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [forceReprocess, setForceReprocess] = useState(false);

  return (
    <div className="space-y-3">
      {image.matched_catalog_key && (
        <div className="py-2 px-3 bg-green-50 border border-green-200 rounded-md text-sm space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
            <span className="text-green-800">
              {MODAL_ALREADY_MATCHED}{' '}
              <code className="text-xs bg-green-100 px-1 py-0.5 rounded">{image.matched_catalog_key}</code>
            </span>
          </div>
          {image.matched_model && (
            <p className="text-xs text-green-600 ml-4">
              {INSTAGRAM_VIA} {image.matched_model}
            </p>
          )}
        </div>
      )}

      {image.post_url && (
        <a
          href={image.post_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full bg-blue-600 text-white text-center py-2 px-4 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          {MODAL_VIEW_ON_INSTAGRAM}
        </a>
      )}

      {matchState === "idle" && !matchError && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => startSingleMatch(image.key, { forceReprocess })}
            className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 transition-colors text-sm font-medium"
          >
            {MODAL_MATCH_THIS_PHOTO}
          </button>
          {image.matched_catalog_key && (
            <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={forceReprocess}
                onChange={(e) => setForceReprocess(e.target.checked)}
                className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
              />
              {ADVANCED_FORCE_REPROCESS}
            </label>
          )}
        </div>
      )}

      {matchError && (
        <div className="py-2 px-4 rounded-md text-sm bg-red-50 text-red-700">
          <p className="font-medium">{matchError}</p>
          <button
            type="button"
            onClick={resetMatch}
            className="text-xs text-purple-600 hover:underline mt-1"
          >
            {MODAL_MATCH_RETRY}
          </button>
        </div>
      )}

      {matchState === "running" && (
        <div className="flex items-center gap-2 py-2 px-4 bg-purple-50 rounded-md text-sm text-purple-700">
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
          {MODAL_MATCH_RUNNING}
          {matchJob && ` ${matchJob.progress}%`}
        </div>
      )}

      {matchState === "done" && matchResult && !matchError && (
        <div
          className={`py-2 px-4 rounded-md text-sm ${matchResult.matched > 0 ? "bg-green-50 text-green-700" : "bg-gray-50 text-gray-600"}`}
        >
          <p className="font-medium">
            {matchResult.matched > 0 ? MODAL_MATCH_RESULT_FOUND : MODAL_MATCH_RESULT_NONE}
            {matchResult.score != null && ` (score: ${matchResult.score.toFixed(2)})`}
          </p>
          <div className="flex gap-2 mt-2">
            {matchResult.matched > 0 && (
              <a href="/processing" className="text-xs text-blue-600 hover:underline">
                {MODAL_MATCH_VIEW_RESULTS}
              </a>
            )}
            <button
              type="button"
              onClick={resetMatch}
              className="text-xs text-purple-600 hover:underline"
            >
              {MODAL_MATCH_RETRY}
            </button>
          </div>
        </div>
      )}

      {matchState === "done" && matchJob?.status === "failed" && (
        <div className="py-2 px-4 rounded-md text-sm bg-red-50 text-red-700">
          <p className="font-medium">
            {MODAL_MATCH_JOB_FAILED_PREFIX} {matchJob.error || MSG_UNKNOWN_ERROR}
          </p>
          <button
            type="button"
            onClick={resetMatch}
            className="text-xs text-purple-600 hover:underline mt-1"
          >
            {MODAL_MATCH_RETRY}
          </button>
        </div>
      )}

      <AdvancedOptions
        isOpen={advancedOpen}
        onToggle={() => setAdvancedOpen(!advancedOpen)}
        providerId={matchOptions.providerId}
        providerModel={matchOptions.providerModel}
        onProviderChange={(providerId, modelId) => {
          updateOption("providerId", providerId);
          updateOption("providerModel", modelId);
        }}
        threshold={matchOptions.threshold}
        onThresholdChange={(v) => updateOption("threshold", v)}
        phashWeight={matchOptions.phashWeight}
        onPhashWeightChange={(v) => updateOption("phashWeight", v)}
        descWeight={matchOptions.descWeight}
        onDescWeightChange={(v) => updateOption("descWeight", v)}
        visionWeight={matchOptions.visionWeight}
        onVisionWeightChange={(v) => updateOption("visionWeight", v)}
        maxWorkers={matchOptions.maxWorkers}
        onMaxWorkersChange={(v) => updateOption("maxWorkers", v)}
        weightsError={weightsError}
        onReset={resetOptions}
      />
    </div>
  );
}
