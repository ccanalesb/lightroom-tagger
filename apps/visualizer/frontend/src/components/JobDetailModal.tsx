import { useState } from 'react';
import type { Job } from '../types/job';
import {
  MODAL_CLOSE,
  JOB_DETAILS_TITLE,
  JOB_DETAILS_PROGRESS,
  JOB_DETAILS_CURRENT_STEP,
  JOB_DETAILS_METADATA,
  JOB_DETAILS_RESULT,
  JOB_DETAILS_ERROR,
  JOB_DETAILS_LOGS,
  JOB_CONFIG_METHOD,
  JOB_CONFIG_DATE_WINDOW,
  JOB_CONFIG_VISION_MODEL,
  JOB_CONFIG_WEIGHTS,
} from '../constants/strings';

interface JobDetailModalProps {
  job: Job;
  onClose: () => void;
}

export function JobDetailModal({ job, onClose }: JobDetailModalProps) {
  const [logs, setLogs] = useState<string[]>([]);

  // Status badge color
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'failed': return 'bg-red-100 text-red-800 border-red-200';
      case 'running': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'cancelled': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
  };

  // Progress bar
  const renderProgress = () => {
    if (job.progress === undefined) return null;

    return (
      <div className="mt-4">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">{JOB_DETAILS_PROGRESS}</span>
          <span className="font-medium">{job.progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${
              job.status === 'completed' ? 'bg-green-500' :
              job.status === 'failed' ? 'bg-red-500' :
              job.status === 'running' ? 'bg-blue-500' : 'bg-gray-400'
            }`}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-bold">{JOB_DETAILS_TITLE}</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded hover:bg-gray-100"
          >
            {MODAL_CLOSE}
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Job Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">ID:</span>
              <p className="font-mono text-xs break-all">{job.id}</p>
            </div>
            <div>
              <span className="text-gray-500">Type:</span>
              <p className="font-medium">{job.type}</p>
            </div>
            <div>
              <span className="text-gray-500">Status:</span>
              <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getStatusColor(job.status)}`}>
                {job.status}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Created:</span>
              <p>{new Date(job.created_at).toLocaleString()}</p>
            </div>
          </div>

          {/* Progress */}
          {renderProgress()}

          {/* Current Step */}
          {job.current_step && (
            <div className="bg-blue-50 p-3 rounded">
              <span className="text-sm text-blue-600 font-medium">{JOB_DETAILS_CURRENT_STEP}:</span>
              <p className="text-sm text-blue-800">{job.current_step}</p>
            </div>
          )}

          {/* Metadata */}
          {job.metadata && Object.keys(job.metadata).length > 0 && (
            <div className="border rounded p-3">
              <h4 className="font-medium text-sm mb-2">{JOB_DETAILS_METADATA}</h4>
              <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                {JSON.stringify(job.metadata, null, 2)}
              </pre>
            </div>
          )}

          {/* Job Configuration */}
          {job.result && (job.result.method || job.result.vision_model) && (
            <div className="border border-purple-200 rounded p-3 bg-purple-50">
              <h4 className="font-medium text-sm mb-2 text-purple-800">Configuration</h4>
              <div className="text-sm space-y-1">
                {job.result.method && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">{JOB_CONFIG_METHOD}:</span>
                    <span className="font-medium">{job.result.method}</span>
                  </div>
                )}
                {job.result.date_window_days && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">{JOB_CONFIG_DATE_WINDOW}:</span>
                    <span className="font-medium">{job.result.date_window_days} days</span>
                  </div>
                )}
                {job.result.vision_model && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">{JOB_CONFIG_VISION_MODEL}:</span>
                    <span className="font-medium font-mono">{job.result.vision_model}</span>
                  </div>
                )}
                {job.result.weights && (
                  <div>
                    <span className="text-gray-600">{JOB_CONFIG_WEIGHTS}:</span>
                    <div className="mt-1 pl-4 text-xs space-y-0.5">
                      <div>pHash: {(job.result.weights.phash * 100).toFixed(0)}%</div>
                      <div>Description: {(job.result.weights.description * 100).toFixed(0)}%</div>
                      <div>Vision: {(job.result.weights.vision * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Result */}
          {job.result && (
            <div className="border border-green-200 rounded p-3 bg-green-50">
              <h4 className="font-medium text-sm mb-2 text-green-800">{JOB_DETAILS_RESULT}</h4>
              <pre className="text-xs bg-white p-2 rounded overflow-x-auto">
                {JSON.stringify(job.result, null, 2)}
              </pre>
            </div>
          )}

          {/* Error */}
          {job.error && (
            <div className="border border-red-200 rounded p-3 bg-red-50">
              <h4 className="font-medium text-sm mb-2 text-red-800">{JOB_DETAILS_ERROR}</h4>
              <p className="text-sm text-red-700 font-mono">{job.error}</p>
            </div>
          )}

          {/* Logs */}
          {job.logs && job.logs.length > 0 && (
            <div className="border rounded p-3">
              <h4 className="font-medium text-sm mb-2">{JOB_DETAILS_LOGS}</h4>
              <div className="bg-gray-900 text-gray-100 p-3 rounded font-mono text-xs max-h-48 overflow-y-auto">
                {job.logs.map((log, idx) => (
                  <div key={idx} className="mb-1">
                    <span className="text-gray-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <span className={`ml-2 ${
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'warn' ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      [{log.level}]
                    </span>
                    <span className="ml-2">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
