import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import {
  MatchDetailModal,
  MULTI_CANDIDATE_REJECT_ADVANCE_MS,
} from '../MatchDetailModal';
import { MatchingAPI } from '../../../../services/api';
import type { Match, MatchGroup } from '../../../../services/api';
import {
  MATCH_REJECT,
  MATCH_REJECT_CONFIRM,
  MATCH_DETAIL_REJECTED_LABEL,
  MATCH_VALIDATE,
  MATCH_DETAIL_REJECTED_AUTOCLOSE_MS,
} from '../../../../constants/strings';

vi.mock('../../../../services/api', () => ({
  MatchingAPI: {
    reject: vi.fn(() => Promise.resolve({ rejected: true })),
    validate: vi.fn(() => Promise.resolve({ validated: true })),
  },
}));

function baseMatch(over: Partial<Match> = {}): Match {
  return {
    instagram_key: 'ig-1',
    catalog_key: 'cat-1',
    score: 0.91,
    ...over,
  };
}

describe('MatchDetailModal reject flow', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(MatchingAPI.reject).mockResolvedValue({ rejected: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('multi-candidate: shows Rejected badge, disables actions, then advances after delay', async () => {
    const match1 = baseMatch({ catalog_key: 'cat-a', score: 0.91 });
    const match2 = baseMatch({ catalog_key: 'cat-b', score: 0.82 });
    const group: MatchGroup = {
      instagram_key: match1.instagram_key,
      candidates: [match1, match2],
      best_score: match1.score,
      candidate_count: 2,
      has_validated: false,
    };
    const onCandidateChange = vi.fn();
    const onClose = vi.fn();

    render(
      <MatchDetailModal
        match={match1}
        group={group}
        onClose={onClose}
        onCandidateChange={onCandidateChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: MATCH_REJECT }));
    fireEvent.click(screen.getByRole('button', { name: MATCH_REJECT_CONFIRM }));

    await waitFor(() => {
      expect(screen.getByText(MATCH_DETAIL_REJECTED_LABEL)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: MATCH_VALIDATE })).toBeDisabled();
    expect(screen.getByRole('button', { name: MATCH_REJECT })).toBeDisabled();
    expect(onCandidateChange).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(MULTI_CANDIDATE_REJECT_ADVANCE_MS);
    });

    expect(onCandidateChange).toHaveBeenCalledTimes(1);
    expect(onCandidateChange).toHaveBeenCalledWith(match2);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('single-candidate: calls onClose after auto-close delay', async () => {
    const match1 = baseMatch();
    const group: MatchGroup = {
      instagram_key: match1.instagram_key,
      candidates: [match1],
      best_score: match1.score,
      candidate_count: 1,
      has_validated: false,
    };
    const onClose = vi.fn();

    render(<MatchDetailModal match={match1} group={group} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: MATCH_REJECT }));
    fireEvent.click(screen.getByRole('button', { name: MATCH_REJECT_CONFIRM }));

    await waitFor(() => {
      expect(screen.getByText(MATCH_DETAIL_REJECTED_LABEL)).toBeInTheDocument();
    });

    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(MATCH_DETAIL_REJECTED_AUTOCLOSE_MS);
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
