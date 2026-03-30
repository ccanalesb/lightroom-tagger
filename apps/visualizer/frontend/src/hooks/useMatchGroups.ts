import { useState, useCallback } from 'react';
import type { Match, MatchGroup } from '../services/api';
import { MatchingAPI } from '../services/api';

export function useMatchGroups() {
  const [matchGroups, setMatchGroups] = useState<MatchGroup[]>([]);
  const [total, setTotal] = useState(0);

  const fetchGroups = useCallback(async (limit = 100) => {
    const data = await MatchingAPI.list(limit);
    setMatchGroups(data.match_groups ?? []);
    setTotal(data.total);
  }, []);

  const handleValidationChange = useCallback((match: Match, validated: boolean) => {
    setMatchGroups((prev) =>
      prev.map((g) => {
        if (g.instagram_key !== match.instagram_key) return g;
        const candidates = g.candidates.map((c) =>
          c.catalog_key === match.catalog_key && c.instagram_key === match.instagram_key
            ? { ...c, validated_at: validated ? new Date().toISOString() : undefined }
            : c
        );
        return {
          ...g,
          candidates,
          has_validated: candidates.some((c) => c.validated_at),
        };
      })
    );
  }, []);

  const handleRejected = useCallback((match: Match) => {
    setMatchGroups((prev) =>
      prev.flatMap((g) => {
        if (g.instagram_key !== match.instagram_key) return [g];
        const remaining = g.candidates.filter(
          (c) => !(c.catalog_key === match.catalog_key && c.instagram_key === match.instagram_key)
        );
        if (remaining.length === 0) return [];
        return [
          {
            ...g,
            candidates: remaining,
            candidate_count: remaining.length,
            best_score: Math.max(...remaining.map((c) => c.score)),
            has_validated: remaining.some((c) => c.validated_at),
          },
        ];
      })
    );
    setTotal((t) => t - 1);
  }, []);

  return { matchGroups, total, fetchGroups, handleValidationChange, handleRejected };
}
