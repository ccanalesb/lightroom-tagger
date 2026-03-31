import { useCallback, useEffect, useRef, useState } from "react";
import type { Job } from "../services/api";
import { JobsAPI } from "../services/api";
import { useMatchOptions } from "../stores/matchOptionsContext";

export type SingleMatchState = "idle" | "running" | "done";

export function useSingleMatch(imageKey: string) {
  const { options: matchOptions } = useMatchOptions();
  const [matchState, setMatchState] = useState<SingleMatchState>("idle");
  const [matchJob, setMatchJob] = useState<Job | null>(null);
  const [matchResult, setMatchResult] = useState<{
    matched: number;
    score?: number;
  } | null>(null);
  const [matchError, setMatchError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const resetMatch = useCallback(() => {
    clearPoll();
    setMatchState("idle");
    setMatchJob(null);
    setMatchResult(null);
    setMatchError(null);
  }, [clearPoll]);

  useEffect(() => {
    resetMatch();
    return clearPoll;
  }, [imageKey, resetMatch, clearPoll]);

  const pollJob = useCallback(
    (jobId: string) => {
      clearPoll();
      pollIntervalRef.current = setInterval(async () => {
        try {
          const job = await JobsAPI.get(jobId);
          setMatchJob(job);
          if (job.status === "completed" || job.status === "failed") {
            clearPoll();
            setMatchState("done");
            setMatchError(null);
            if (job.result) {
              setMatchResult({
                matched: job.result.matched ?? 0,
                score: job.result.best_score,
              });
            }
          }
        } catch {
          clearPoll();
          setMatchState("done");
          setMatchError(
            "Could not refresh match status. Check your connection and try again.",
          );
        }
      }, 2000);
    },
    [clearPoll],
  );

  const startSingleMatch = useCallback(
    async (key: string, options?: { forceReprocess?: boolean }) => {
      setMatchState("running");
      setMatchResult(null);
      setMatchError(null);
      try {
        const metadata: Record<string, unknown> = {
          media_key: key,
          threshold: matchOptions.threshold,
          weights: {
            phash: matchOptions.phashWeight,
            description: matchOptions.descWeight,
            vision: matchOptions.visionWeight,
          },
          ...(matchOptions.providerId
            ? {}
            : { vision_model: matchOptions.selectedModel || undefined }),
        };
        if (matchOptions.providerId) {
          metadata.provider_id = matchOptions.providerId;
          if (matchOptions.providerModel) {
            metadata.provider_model = matchOptions.providerModel;
          }
        }
        if (options?.forceReprocess) metadata.force_reprocess = true;
        const job = await JobsAPI.create("vision_match", metadata);
        setMatchJob(job);
        pollJob(job.id);
      } catch (err) {
        setMatchState("idle");
        setMatchError(
          err instanceof Error ? err.message : "Failed to start match",
        );
        console.error("Failed to start match:", err);
      }
    },
    [matchOptions, pollJob],
  );

  return {
    matchState,
    matchJob,
    matchResult,
    matchError,
    startSingleMatch,
    resetMatch,
  };
}
