import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { JobQueueTab } from '../JobQueueTab';
import type { Job } from '../../../types/job';

vi.mock('../../jobs/JobDetailModal', () => ({
  JobDetailModal: () => null,
}));

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    cancel: vi.fn(),
    retry: vi.fn(),
  },
}));

function makeJobs(count: number, offset = 0): Job[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `job-${offset + i}`,
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
  } as Job));
}

describe('JobQueueTab pagination', () => {
  it('hides the Pagination when total <= limit', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(10)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 10 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.queryByLabelText('Previous page')).toBeNull();
    expect(screen.queryByLabelText('Next page')).toBeNull();
  });

  it('shows the Pagination when total > limit', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 175 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.getByLabelText('Next page')).toBeTruthy();
    expect(screen.getByText(/Showing 1–50 of 175/)).toBeTruthy();
  });

  it('clicking Next invokes onOffsetChange with offset + limit', () => {
    const onOffsetChange = vi.fn();
    render(
      <JobQueueTab
        jobs={makeJobs(50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 0, limit: 50, total: 175 }}
        onOffsetChange={onOffsetChange}
      />
    );
    fireEvent.click(screen.getByLabelText('Next page'));
    expect(onOffsetChange).toHaveBeenCalledWith(50);
  });

  it('shows correct "Showing X–Y of Z" label on page 2', () => {
    render(
      <JobQueueTab
        jobs={makeJobs(50, 50)}
        setJobs={vi.fn()}
        jobsLoading={false}
        connected={true}
        onRefreshJobs={vi.fn()}
        pagination={{ offset: 50, limit: 50, total: 175 }}
        onOffsetChange={vi.fn()}
      />
    );
    expect(screen.getByText(/Showing 51–100 of 175/)).toBeTruthy();
  });
});
