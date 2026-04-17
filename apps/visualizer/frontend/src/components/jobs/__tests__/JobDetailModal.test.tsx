import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { JobDetailModal } from '../JobDetailModal';
import type { Job } from '../../../types/job';

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
    mockGet.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders identity row (id, type, status) immediately from the list-row job, even while loading', () => {
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
      () => new Promise<Job>((resolve) => { resolveFetch = resolve; })
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
});
