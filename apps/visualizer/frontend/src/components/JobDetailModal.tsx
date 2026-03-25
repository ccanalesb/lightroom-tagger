import { useState, useEffect } from 'react';
import { useSocketStore } from '../stores/socketStore';
import { JobsAPI } from '../services/api';
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
 onJobUpdate?: (updatedJob: Job) => void;
}

export function JobDetailModal({ job, onClose, onJobUpdate }: JobDetailModalProps) {
 const [localJob, setLocalJob] = useState<Job>(job);
 const socket = useSocketStore(state => state.socket);

 // Fetch fresh job data when modal opens to ensure logs are loaded
 useEffect(() => {
   JobsAPI.get(job.id)
     .then(freshJob => {
       setLocalJob(freshJob);
     })
     .catch(err => {
       console.error('Failed to fetch job details:', err);
     });
 }, [job.id]);

 // Subscribe to job updates via WebSocket
 useEffect(() => {
   if (!socket) return;

   // Subscribe to this specific job
   socket.emit('subscribe_job', { job_id: job.id });

   // Listen for job updates
   const handleJobUpdate = (updatedJob: Job) => {
     if (updatedJob.id === job.id) {
       setLocalJob(updatedJob);
       onJobUpdate?.(updatedJob);
     }
   };

   socket.on('job_updated', handleJobUpdate);

   return () => {
     socket.emit('unsubscribe_job', { job_id: job.id });
     socket.off('job_updated', handleJobUpdate);
   };
 }, [socket, job.id, onJobUpdate]);

 // Use localJob if available, otherwise fall back to prop
 const displayJob = localJob.id === job.id ? localJob : job;

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
   if (displayJob.progress === undefined) return null;

   return (
     <div className="mt-4">
       <div className="flex justify-between text-sm mb-1">
         <span className="text-gray-600">{JOB_DETAILS_PROGRESS}</span>
         <span className="font-medium">{displayJob.progress}%</span>
       </div>
       <div className="w-full bg-gray-200 rounded-full h-2">
         <div
           className={`h-2 rounded-full transition-all duration-300 ${
             displayJob.status === 'completed' ? 'bg-green-500' :
             displayJob.status === 'failed' ? 'bg-red-500' :
             displayJob.status === 'running' ? 'bg-blue-500' : 'bg-gray-400'
           }`}
           style={{ width: `${displayJob.progress}%` }}
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
             <p className="font-mono text-xs break-all">{displayJob.id}</p>
           </div>
           <div>
             <span className="text-gray-500">Type:</span>
             <p className="font-medium">{displayJob.type}</p>
           </div>
           <div>
             <span className="text-gray-500">Status:</span>
             <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${getStatusColor(displayJob.status)}`}>
               {displayJob.status}
             </span>
           </div>
           <div>
             <span className="text-gray-500">Created:</span>
             <p>{new Date(displayJob.created_at).toLocaleString()}</p>
           </div>
         </div>

         {/* Progress */}
         {renderProgress()}

         {/* Current Step */}
         {displayJob.current_step && (
           <div className="bg-blue-50 p-3 rounded">
             <span className="text-sm text-blue-600 font-medium">{JOB_DETAILS_CURRENT_STEP}:</span>
             <p className="text-sm text-blue-800">{displayJob.current_step}</p>
           </div>
         )}

         {/* Metadata */}
         {displayJob.metadata && Object.keys(displayJob.metadata).length > 0 && (
           <div className="border rounded p-3">
             <h4 className="font-medium text-sm mb-2">{JOB_DETAILS_METADATA}</h4>
             <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
               {JSON.stringify(displayJob.metadata, null, 2)}
             </pre>
           </div>
         )}

         {/* Job Configuration - show from metadata during run, from result when complete */}
         {(displayJob.metadata?.method || displayJob.result?.method) && (
           <div className="border border-purple-200 rounded p-3 bg-purple-50">
             <h4 className="font-medium text-sm mb-2 text-purple-800">Configuration</h4>
             <div className="text-sm space-y-1">
               {(displayJob.metadata?.method || displayJob.result?.method) && (
                 <div className="flex justify-between">
                   <span className="text-gray-600">{JOB_CONFIG_METHOD}:</span>
                   <span className="font-medium">{displayJob.metadata?.method || displayJob.result?.method}</span>
                 </div>
               )}
               {(displayJob.metadata?.date_window_days || displayJob.result?.date_window_days) && (
                 <div className="flex justify-between">
                   <span className="text-gray-600">{JOB_CONFIG_DATE_WINDOW}:</span>
                   <span className="font-medium">{displayJob.metadata?.date_window_days || displayJob.result?.date_window_days} days</span>
                 </div>
               )}
               {(displayJob.metadata?.vision_model || displayJob.result?.vision_model) && (
                 <div className="flex justify-between">
                   <span className="text-gray-600">{JOB_CONFIG_VISION_MODEL}:</span>
                   <span className="font-medium font-mono">{displayJob.metadata?.vision_model || displayJob.result?.vision_model}</span>
                 </div>
               )}
               {(displayJob.metadata?.weights || displayJob.result?.weights) && (
                 <div>
                   <span className="text-gray-600">{JOB_CONFIG_WEIGHTS}:</span>
                   <div className="mt-1 pl-4 text-xs space-y-0.5">
                     <div>pHash: {((displayJob.metadata?.weights?.phash || displayJob.result?.weights?.phash) * 100).toFixed(0)}%</div>
                     <div>Description: {((displayJob.metadata?.weights?.description || displayJob.result?.weights?.description) * 100).toFixed(0)}%</div>
                     <div>Vision: {((displayJob.metadata?.weights?.vision || displayJob.result?.weights?.vision) * 100).toFixed(0)}%</div>
                   </div>
                 </div>
               )}
             </div>
           </div>
         )}

         {/* Result */}
         {displayJob.result && (
           <div className="border border-green-200 rounded p-3 bg-green-50">
             <h4 className="font-medium text-sm mb-2 text-green-800">{JOB_DETAILS_RESULT}</h4>
             <pre className="text-xs bg-white p-2 rounded overflow-x-auto">
               {JSON.stringify(displayJob.result, null, 2)}
             </pre>
           </div>
         )}

         {/* Error */}
         {displayJob.error && (
           <div className="border border-red-200 rounded p-3 bg-red-50">
             <h4 className="font-medium text-sm mb-2 text-red-800">{JOB_DETAILS_ERROR}</h4>
             <p className="text-sm text-red-700 font-mono">{displayJob.error}</p>
           </div>
         )}

         {/* Logs */}
         {displayJob.logs && displayJob.logs.length > 0 && (
           <div className="border rounded p-3">
             <h4 className="font-medium text-sm mb-2">{JOB_DETAILS_LOGS}</h4>
             <div className="bg-gray-900 text-gray-100 p-3 rounded font-mono text-xs max-h-48 overflow-y-auto">
               {displayJob.logs.map((log, idx) => (
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
