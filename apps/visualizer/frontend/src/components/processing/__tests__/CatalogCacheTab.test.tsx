import { Suspense } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { deleteMatching } from '../../../data/cache';
import { CatalogCacheTab } from '../CatalogCacheTab';
import {
  PROCESSING_EMBED_CATALOG_START,
  PROCESSING_JOB_QUEUE_ROUTE,
  PROCESSING_OPEN_JOB_QUEUE,
} from '../../../constants/strings';

const mockCreate = vi.fn();
const mockFetch = vi.fn();

vi.mock('../../../services/api', () => ({
  JobsAPI: {
    create: (...args: unknown[]) => mockCreate(...args),
  },
}));

vi.stubGlobal('fetch', mockFetch);

function renderCatalogCacheTab(props: { onOpenJobQueue?: () => void } = {}) {
  return render(
    <Suspense fallback={null}>
      <CatalogCacheTab {...props} />
    </Suspense>,
  );
}

describe('CatalogCacheTab embed launcher', () => {
  beforeEach(() => {
    deleteMatching(() => true);
    mockCreate.mockReset();
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      json: async () => ({
        total_images: 10,
        cached_images: 5,
        missing: 5,
        cache_size_mb: 100,
        cache_dir: '/tmp/cache',
      }),
    });
  });

  it('renders an embed launcher by default', async () => {
    renderCatalogCacheTab();
    expect(await screen.findByRole('button', { name: PROCESSING_EMBED_CATALOG_START })).toBeTruthy();
  });

  it('enqueues batch_embed_image with the expected payload', async () => {
    mockCreate.mockResolvedValue({ id: 'job-embed', type: 'batch_embed_image' });
    renderCatalogCacheTab();
    fireEvent.click(await screen.findByRole('button', { name: PROCESSING_EMBED_CATALOG_START }));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('batch_embed_image', { image_type: 'catalog' });
    });
    expect(await screen.findByRole('button', { name: PROCESSING_OPEN_JOB_QUEUE })).toBeTruthy();
  });

  it('shows queue action that targets /processing?tab=jobs', async () => {
    mockCreate.mockResolvedValue({ id: 'job-embed', type: 'batch_embed_image' });
    const onOpenJobQueue = vi.fn();
    renderCatalogCacheTab({ onOpenJobQueue });
    fireEvent.click(await screen.findByRole('button', { name: PROCESSING_EMBED_CATALOG_START }));
    const queueButton = await screen.findByRole('button', { name: PROCESSING_OPEN_JOB_QUEUE });
    fireEvent.click(queueButton);
    expect(onOpenJobQueue).toHaveBeenCalledTimes(1);
    expect(PROCESSING_JOB_QUEUE_ROUTE).toBe('/processing?tab=jobs');
  });
});
