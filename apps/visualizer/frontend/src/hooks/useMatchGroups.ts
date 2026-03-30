import { useState, useCallback } from 'react';
import type { Match, MatchGroup } from '../services/api';
import { MatchingAPI } from '../services/api';

export function useMatchGroups() {
  const [matchGroups, setMatchGroups] = useState<MatchGroup[]>([]);
  const [total, setTotal] = useState(0);

  const fetchGroups = useCallback(async (limit = 100) => {
    const data = await MatchingAPI.list(limit);
    setMatchGroups(data.match_groups ?? []);
    setTotal(data.total_groups ?? data.total);
  }, []);

  const handleValidationChange = useCallback((match: Match, validated: boolean) => {
    setMatchGroups((prev) =>
      prev.map((group) => {
        if (group.instagram_key !== match.instagram_key) return group;
        const candidates = group.candidates.map((candidate) =>
          candidate.catalog_key === match.catalog_key && candidate.instagram_key === match.instagram_key
            ? { ...candidate, validated_at: validated ? new Date().toISOString() : undefined }
            : candidate
        );
        return {
          ...group,
          candidates,
          has_validated: candidates.some((candidate) => candidate.validated_at),
        };
      })
    );
  }, []);

  const handleRejected = useCallback((match: Match) => {
    setMatchGroups((prev) => {
      let removedEntireGroup = false;
      const next = prev.flatMap((group) => {
        if (group.instagram_key !== match.instagram_key) return [group];
        const remaining = group.candidates.filter(
          (candidate) =>
            !(
              candidate.catalog_key === match.catalog_key &&
              candidate.instagram_key === match.instagram_key
            )
        );
        if (remaining.length === 0) {
          removedEntireGroup = true;
          return [];
        }
        return [
          {
            ...group,
            candidates: remaining,
            candidate_count: remaining.length,
            best_score: Math.max(...remaining.map((candidate) => candidate.score)),
            has_validated: remaining.some((candidate) => candidate.validated_at),
          },
        ];
      });
      if (removedEntireGroup) {
        setTotal((groupCount) => groupCount - 1);
      }
      return next;
    });
  }, []);

  return { matchGroups, total, fetchGroups, handleValidationChange, handleRejected };
}
