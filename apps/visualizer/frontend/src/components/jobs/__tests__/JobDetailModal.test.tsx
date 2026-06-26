import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { deleteMatching } from '../../../data/cache';
import { JobDetailModal } from '../JobDetailModal';
import type { Job } from '../../../types/job';
import {
  JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE,
  JOB_SKIP_EMPTY_PATH,
  JOB_SKIP_MISSING_FILE,
  JOB_SKIP_NO_DB_ROW,
} from '../../../constants/strings';

const mockGet = vi.fn();
vi.mock('../../../services/api', () => ({
  JobsAPI: {
    get: (...args: unknown[]) => mockGet(...args),
    retry: vi.fn(),
  },
}));

vi.mock('../../../stores/socketStore', () => ({
  useSocketStore: () => null,
}));


function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
    type: 'matching',
    status: 'completed',
    progress: 1,
    current_step: null,
    logs: [],
    logs_total: 0,
    result: null,
    error: null,
    created_at: new Date().toISOString(),
    started_at: null,
    completed_at: null,
    metadata: {},
    ...overrides,
  } as Job;
}

describe('JobDetailModal', () => {
  beforeEach(() => {
    deleteMatching(() => true);
    mockGet.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders identity row (id, type, status) immediately from the list-row job, even while loading', async () => {
    mockGet.mockImplementation(() => new Promise<Job>(() => {}));
    const job = makeJob({ id: 'abc-123', type: 'matching', status: 'running' });
    render(<JobDetailModal job={job} onClose={() => {}} />);
    expect(screen.getByText('abc-123')).toBeTruthy();
    expect(screen.getByText('matching')).toBeTruthy();
    expect(screen.getByText(/running/i)).toBeTruthy();
  });

  it('shows a skeleton for heavy sections while the initial fetch is in flight', async () => {
    let resolveFetch: (value: Job) => void = () => {};
    mockGet.mockImplementationOnce(
      () => new Promise<Job>((resolve) => { resolveFetch = resolve; }),
    );
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    expect(screen.getAllByLabelText(/loading job details/i).length).toBeGreaterThan(0);
    resolveFetch(makeJob({ logs_total: 0 }));
    await waitFor(() => {
      expect(screen.queryAllByLabelText(/loading job details/i).length).toBe(0);
    });
  });

  it('shows an inline fetch-error banner when the initial GET fails, keeping identity row visible', async () => {
    mockGet.mockRejectedValueOnce(new Error('500 Internal Server Error'));
    const job = makeJob({ id: 'id-err', type: 'matching', status: 'failed' });
    render(<JobDetailModal job={job} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(screen.getByText(/could not refresh job details/i)).toBeTruthy();
    expect(screen.getByText('id-err')).toBeTruthy();
  });

  it('initial fetch passes logs_limit: 20', async () => {
    mockGet.mockResolvedValue(makeJob({ logs_total: 5 }));
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('job-1', { logs_limit: 20 });
    });
  });

  it('renders truncated header and Show all button when logs_total > logs.length', async () => {
    const truncatedJob = makeJob({
      logs: Array.from({ length: 20 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 137,
    });
    mockGet.mockResolvedValue(truncatedJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/Logs \(20 of 137\)/)).toBeTruthy();
    });
    expect(screen.getByText(/Show all 137 logs/)).toBeTruthy();
  });

  it('clicking Show all refetches with logs_limit: 0 and hides the button', async () => {
    const truncatedJob = makeJob({
      logs: Array.from({ length: 20 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 50,
    });
    const fullJob = makeJob({
      logs: Array.from({ length: 50 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 50,
    });
    mockGet
      .mockResolvedValueOnce(truncatedJob)
      .mockResolvedValueOnce(fullJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    const showAll = await screen.findByText(/Show all 50 logs/);
    fireEvent.click(showAll);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('job-1', { logs_limit: 0 });
    });
    await waitFor(() => {
      expect(screen.queryByText(/Show all 50 logs/)).toBeNull();
    });
  });

  it('does not render the Show all button when logs_total equals logs.length', async () => {
    const exactJob = makeJob({
      logs: Array.from({ length: 5 }, (_, i) => ({
        timestamp: new Date().toISOString(),
        level: 'info' as const,
        message: `m${i}`,
      })),
      logs_total: 5,
    });
    mockGet.mockResolvedValue(exactJob);
    render(<JobDetailModal job={makeJob()} onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/^Logs$/)).toBeTruthy();
    });
    expect(screen.queryByText(/Show all/)).toBeNull();
  });

  it('renders grouped embed diagnostics for batch_embed_image jobs', async () => {
    mockGet.mockResolvedValue(
      makeJob({
        type: 'batch_embed_image',
        result: {
          embedded: 2,
          skipped: 4,
          failed: 1,
          total: 7,
          skip_reason_counts: {
            no_row: 1,
            empty_path: 1,
            unresolved_or_missing: 2,
            encode_failed: 1,
          },
        },
      }),
    );
    render(<JobDetailModal job={makeJob({ type: 'batch_embed_image' })} onClose={() => {}} />);

    expect(await screen.findByText(JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE)).toBeTruthy();
    expect(screen.getByText(JOB_SKIP_NO_DB_ROW).parentElement).toHaveTextContent('1');
    expect(screen.getByText(JOB_SKIP_EMPTY_PATH).parentElement).toHaveTextContent('1');
    expect(screen.getByText(JOB_SKIP_MISSING_FILE).parentElement).toHaveTextContent('2');
    expect(screen.queryByText('Encode failed')).toBeNull();
  });

  it('embed diagnostics hidden when only encode_failed is positive', async () => {
    mockGet.mockResolvedValue(
      makeJob({
        type: 'batch_embed_image',
        result: {
          embedded: 0,
          skipped: 5,
          failed: 0,
          total: 5,
          skip_reason_counts: {
            no_row: 0,
            empty_path: 0,
            unresolved_or_missing: 0,
            encode_failed: 5,
          },
        },
      }),
    );
    render(<JobDetailModal job={makeJob({ type: 'batch_embed_image' })} onClose={() => {}} />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalled();
    });
    expect(screen.queryByText(JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE)).toBeNull();
  });

  it('embed diagnostics omits zero buckets', async () => {
    mockGet.mockResolvedValue(
      makeJob({
        type: 'batch_embed_image',
        result: {
          embedded: 0,
          skipped: 3,
          failed: 0,
          total: 3,
          skip_reason_counts: {
            no_row: 0,
            empty_path: 3,
            unresolved_or_missing: 0,
          },
        },
      }),
    );
    render(<JobDetailModal job={makeJob({ type: 'batch_embed_image' })} onClose={() => {}} />);

    expect(await screen.findByText(JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE)).toBeTruthy();
    expect(screen.getByText(JOB_SKIP_EMPTY_PATH).parentElement).toHaveTextContent('3');
    expect(screen.queryByText(JOB_SKIP_NO_DB_ROW)).toBeNull();
    expect(screen.queryByText(JOB_SKIP_MISSING_FILE)).toBeNull();
  });

  it('renders grouped path diagnostics for batch_describe jobs', async () => {
    mockGet.mockResolvedValue(
      makeJob({
        type: 'batch_describe',
        result: {
          described: 0,
          skipped: 2,
          failed: 0,
          total: 2,
          skip_reason_counts: {
            no_row: 0,
            empty_path: 1,
            unresolved_or_missing: 1,
            encode_failed: 0,
          },
        },
      }),
    );
    render(<JobDetailModal job={makeJob({ type: 'batch_describe' })} onClose={() => {}} />);

    expect(await screen.findByText(JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE)).toBeTruthy();
    expect(screen.getByText(JOB_SKIP_EMPTY_PATH).parentElement).toHaveTextContent('1');
    expect(screen.getByText(JOB_SKIP_MISSING_FILE).parentElement).toHaveTextContent('1');
  });

  it('renders grouped path diagnostics for vision_match jobs', async () => {
    mockGet.mockResolvedValue(
      makeJob({
        type: 'vision_match',
        result: {
          processed: 0,
          matched: 0,
          skipped: 3,
          skip_reason_counts: {
            no_row: 0,
            empty_path: 0,
            unresolved_or_missing: 3,
            encode_failed: 0,
          },
        },
      }),
    );
    render(<JobDetailModal job={makeJob({ type: 'vision_match' })} onClose={() => {}} />);

    expect(await screen.findByText(JOB_DETAILS_EMBED_DIAGNOSTICS_TITLE)).toBeTruthy();
    expect(screen.getByText(JOB_SKIP_MISSING_FILE).parentElement).toHaveTextContent('3');
  });
});
