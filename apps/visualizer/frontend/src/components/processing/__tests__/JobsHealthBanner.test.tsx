import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { JobsHealthBanner } from '../JobsHealthBanner';

const mockHealth = vi.fn();

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    health: () => mockHealth(),
  },
}));

describe('JobsHealthBanner', () => {
  beforeEach(() => {
    mockHealth.mockReset();
  });

  it('renders nothing when catalog is available', async () => {
    mockHealth.mockResolvedValue({
      library_db: { path: '/tmp/library.db', source: 'env', exists: true, reason: null },
      jobs_requiring_catalog: ['batch_describe'],
      catalog_available: true,
    });

    const { container } = render(<JobsHealthBanner pollIntervalMs={0} />);
    await waitFor(() => expect(mockHealth).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('renders the unavailable banner with reason and blocked job types', async () => {
    mockHealth.mockResolvedValue({
      library_db: {
        path: '/missing/library.db',
        source: 'env',
        exists: false,
        reason: 'LIBRARY_DB points to a missing file.',
      },
      jobs_requiring_catalog: ['batch_describe', 'vision_match'],
      catalog_available: false,
    });

    render(<JobsHealthBanner pollIntervalMs={0} />);
    const banner = await screen.findByTestId('jobs-health-banner-unavailable');
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain('Catalog unavailable');
    expect(banner.textContent).toContain('LIBRARY_DB points to a missing file.');
    expect(banner.textContent).toContain('batch_describe');
    expect(banner.textContent).toContain('vision_match');
    expect(banner.textContent).toContain('/missing/library.db');
  });

  it('renders an error banner when the health endpoint itself fails', async () => {
    mockHealth.mockRejectedValue(new Error('network down'));

    render(<JobsHealthBanner pollIntervalMs={0} />);
    const banner = await screen.findByTestId('jobs-health-banner-error');
    expect(banner.textContent).toContain('network down');
  });
});
