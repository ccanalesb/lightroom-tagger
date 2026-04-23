import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Suspense } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

import { deleteMatching } from '../../../data/cache';
import { AnalyzeTab } from '../AnalyzeTab';

// Minimal MatchOptions provider the component expects. We stub it directly
// rather than mounting the real provider so the test stays focused on the
// submit-feedback contract introduced in fix #1.
vi.mock('../../../stores/matchOptionsContext', () => ({
  useMatchOptions: () => ({
    options: { maxWorkers: 4 },
    updateOption: vi.fn(),
  }),
}));

// Provider-select is unrelated to submission feedback — render a no-op.
vi.mock('../../ui/ProviderModelSelect', () => ({
  ProviderModelSelect: () => null,
}));
vi.mock('../../matching/WorkerSlider', () => ({
  WorkerSlider: () => null,
}));

const mockCreate = vi.fn();
const mockListPerspectives = vi.fn();
const mockGetDefaults = vi.fn();

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mockCreate(...args),
  },
  PerspectivesAPI: {
    list: (...args: unknown[]) => mockListPerspectives(...args),
  },
  ProvidersAPI: {
    getDefaults: (...args: unknown[]) => mockGetDefaults(...args),
  },
}));

function renderAnalyzeTab() {
  return render(
    <Suspense fallback={null}>
      <AnalyzeTab />
    </Suspense>,
  );
}

describe('AnalyzeTab submit UX (fix #1)', () => {
  beforeEach(() => {
    deleteMatching(() => true);
    mockCreate.mockReset();
    mockListPerspectives.mockReset();
    mockGetDefaults.mockReset();
    mockListPerspectives.mockResolvedValue([
      { slug: 'street', display_name: 'Street' },
    ]);
    mockGetDefaults.mockResolvedValue({ description: { provider: 'ollama', model: 'llava' } });
  });

  it('shows an inline success banner (not an alert) after submission', async () => {
    mockCreate.mockResolvedValue({ id: 'abc12345-job', type: 'batch_analyze' });

    renderAnalyzeTab();

    // Wait for the mounted async effects (perspectives + provider defaults)
    // to settle so React doesn't complain about act() wrapping.
    await screen.findByText(/Street/);

    const primary = screen.getByRole('button', { name: /^Analyze/i });
    fireEvent.click(primary);

    const banner = await screen.findByTestId('analyze-status-banner');
    expect(banner.getAttribute('data-tone')).toBe('success');
    expect(banner.textContent).toMatch(/abc12345/);
  });

  it('shows an inline error banner when the POST fails', async () => {
    mockCreate.mockRejectedValue(new Error('boom'));

    renderAnalyzeTab();
    await screen.findByText(/Street/);

    fireEvent.click(screen.getByRole('button', { name: /^Analyze/i }));

    const banner = await screen.findByTestId('analyze-status-banner');
    expect(banner.getAttribute('data-tone')).toBe('error');
    expect(banner.textContent).toMatch(/boom/);
  });

  it('only fires one POST even when the button is clicked three times rapidly', async () => {
    // Delay the resolution so the second and third clicks land while the
    // first is still in-flight. This is the real-world scenario the user
    // hit: a slow backend + no visual feedback + panicked re-clicks.
    let resolveCreate: (v: unknown) => void = () => {};
    mockCreate.mockImplementation(
      () => new Promise((resolve) => { resolveCreate = resolve; }),
    );

    renderAnalyzeTab();
    await screen.findByText(/Street/);

    const primary = screen.getByRole('button', { name: /^Analyze/i });
    fireEvent.click(primary);
    fireEvent.click(primary);
    fireEvent.click(primary);

    expect(mockCreate).toHaveBeenCalledTimes(1);

    // Resolving closes the submission so subsequent clicks work again.
    await act(async () => {
      resolveCreate({ id: 'first-job' });
    });
    await waitFor(() => expect(screen.getByTestId('analyze-status-banner')).toBeTruthy());
  });

  it('blocks describe-only and score-only clicks while a submission is in flight', async () => {
    let resolveCreate: (v: unknown) => void = () => {};
    mockCreate.mockImplementation(
      () => new Promise((resolve) => { resolveCreate = resolve; }),
    );

    renderAnalyzeTab();
    await screen.findByText(/Street/);

    // Open the advanced panel *before* submitting so the side buttons exist
    // in the DOM and the assertions don't race with conditional rendering.
    fireEvent.click(screen.getByRole('button', { name: /Advanced options/i }));
    const describeBtn = await screen.findByRole('button', { name: /Generate Descriptions only/i });
    const scoreBtn = await screen.findByRole('button', { name: /Run scoring only/i });

    // Start an analyze — both side buttons should now be disabled.
    fireEvent.click(screen.getByRole('button', { name: /^Analyze/i }));
    expect(describeBtn.hasAttribute('disabled')).toBe(true);
    expect(scoreBtn.hasAttribute('disabled')).toBe(true);

    fireEvent.click(describeBtn);
    fireEvent.click(scoreBtn);

    expect(mockCreate).toHaveBeenCalledTimes(1); // still just the analyze

    await act(async () => {
      resolveCreate({ id: 'first-job' });
    });
  });
});
