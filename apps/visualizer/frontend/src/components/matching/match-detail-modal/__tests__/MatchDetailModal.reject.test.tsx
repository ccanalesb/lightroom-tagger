import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MatchDetailModal } from '../MatchDetailModal';
import { MatchingAPI } from '../../../../services/api';
import type { Match, MatchGroup } from '../../../../services/api';
import { MATCH_REJECT, MATCH_REJECT_CONFIRM, MATCH_VALIDATE } from '../../../../constants/strings';

vi.mock('../../../../services/api', () => ({
  MatchingAPI: {
    reject: vi.fn(() => Promise.resolve({ rejected: true })),
    validate: vi.fn(() => Promise.resolve({ validated: true })),
  },
  DescriptionsAPI: {
    get: vi.fn(() => Promise.resolve({ description: null })),
  },
  ProvidersAPI: {
    getDefaults: vi.fn(() => Promise.resolve({ description: null, matching: null })),
  },
  JobsAPI: {
    create: vi.fn(() => Promise.resolve({ id: 'job-1' })),
  },
}));

vi.mock('../../../../hooks/useJobSocket', () => ({
  useJobSocket: vi.fn(),
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
    vi.mocked(MatchingAPI.reject).mockResolvedValue({ rejected: true });
    vi.mocked(MatchingAPI.validate).mockResolvedValue({ validated: true });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('multi-candidate: reject advances to the next candidate immediately', async () => {
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
      expect(onCandidateChange).toHaveBeenCalledWith(match2);
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('single-candidate: reject closes the modal', async () => {
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
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it('validate closes the modal', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: MATCH_VALIDATE }));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
