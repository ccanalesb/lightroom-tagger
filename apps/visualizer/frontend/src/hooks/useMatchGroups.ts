import { useState, useCallback } from 'react';
import type { Match, MatchGroup } from '../services/api';
import { MatchingAPI } from '../services/api';

export function useMatchGroups() {
  const [matchGroups, setMatchGroups] = useState<MatchGroup[]>([]);
  const [total, setTotal] = useState(0);

  const fetchGroups = useCallback(async (limit = 100, offset = 0) => {
    const data = await MatchingAPI.list(limit, offset);
    if (offset === 0) {
      setMatchGroups(data.match_groups ?? []);
      setTotal(data.total_groups ?? data.total);
    } else {
      setMatchGroups((prev) => {
        const next = [...prev];
        for (const g of data.match_groups ?? []) {
          const idx = next.findIndex((existing) => existing.instagram_key === g.instagram_key);
          if (idx >= 0) next[idx] = g;
          else next.push(g);
        }
        return next;
      });
    }
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
    setMatchGroups((prev) =>
      prev.flatMap((group) => {
        if (group.instagram_key !== match.instagram_key) return [group];
        const remaining = group.candidates.filter(
          (candidate) =>
            !(
              candidate.catalog_key === match.catalog_key &&
              candidate.instagram_key === match.instagram_key
            )
        );
        if (remaining.length === 0) {
          return [
            {
              ...group,
              candidates: [],
              candidate_count: 0,
              best_score: 0,
              has_validated: false,
              all_rejected: true,
            },
          ];
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
      })
    );
  }, []);

  return { matchGroups, total, fetchGroups, handleValidationChange, handleRejected };
}
