import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MatchingPage } from '../MatchingPage';

const fetchMock = vi.fn();

function mockApiResponses(models: { name: string; default: boolean }[]) {
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url.includes('/vision-models')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ models, fallback: false }),
      });
    }
    if (url.includes('/jobs/active')) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (url.includes('/jobs/') && init?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: 'test-job-id',
          type: 'vision_match',
          status: 'pending',
          metadata: JSON.parse(init.body as string).metadata,
        }),
      });
    }
    if (url.includes('/matches')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ matches: [], total: 0 }),
      });
    }
    if (url.includes('/cache/status')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          total_images: 10,
          cached_images: 10,
          missing: 0,
          cache_size_mb: 5,
          cache_dir: '/tmp',
        }),
      });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
}

describe('MatchingPage model selection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = fetchMock;
  });

  it('should send the first available model when no default exists', async () => {
    mockApiResponses([{ name: 'gemma3:27b-cloud', default: false }]);

    render(
      <MemoryRouter>
        <MatchingPage />
      </MemoryRouter>
    );

    const runBtn = await screen.findByText('Run Matching');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText('Start')).toBeTruthy();
    });

    const startBtn = screen.getByText('Start');
    fireEvent.click(startBtn);

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([url, opts]: [string, RequestInit?]) =>
          url.includes('/jobs/') && opts?.method === 'POST'
      );
      expect(postCall).toBeTruthy();
      const body = JSON.parse(postCall![1].body as string);
      expect(body.metadata.vision_model).toBe('gemma3:27b-cloud');
    }, { timeout: 3000 });
  });

  it('should send the default model when one exists', async () => {
    mockApiResponses([
      { name: 'gemma3:4b', default: false },
      { name: 'gemma3:27b', default: true },
    ]);

    render(
      <MemoryRouter>
        <MatchingPage />
      </MemoryRouter>
    );

    const runBtn = await screen.findByText('Run Matching');
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(screen.getByText('Start')).toBeTruthy();
    });

    const startBtn = screen.getByText('Start');
    fireEvent.click(startBtn);

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([url, opts]: [string, RequestInit?]) =>
          url.includes('/jobs/') && opts?.method === 'POST'
      );
      expect(postCall).toBeTruthy();
      const body = JSON.parse(postCall![1].body as string);
      expect(body.metadata.vision_model).toBe('gemma3:27b');
    }, { timeout: 3000 });
  });
});
