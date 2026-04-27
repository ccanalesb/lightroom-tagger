import { Suspense } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { deleteMatching } from '../../../data/cache';
import { CatalogCacheTab } from '../CatalogCacheTab';
import {
  ADVANCED_OPTIONS_TITLE,
  ADVANCED_WEIGHTS_TITLE,
  CATALOG_CACHE_BUILD_CTA,
  CATALOG_CACHE_BUILD_SUCCESS,
  CATALOG_CACHE_EMBED_CATALOG_LABEL,
  CATALOG_CACHE_PIPELINE_TITLE,
  CATALOG_CACHE_SIMILARITY_BEST_MATCH_PCT,
  CATALOG_CACHE_SIMILARITY_PREVIEW_TITLE,
  CATALOG_CACHE_SIMILARITY_TOTAL_GROUPS_LABEL,
  PROCESSING_JOB_QUEUE_ROUTE,
  PROCESSING_OPEN_JOB_QUEUE,
} from '../../../constants/strings';

const mockCreate = vi.fn();
const mockFetch = vi.fn();
const mockListCatalogSimilarityGroups = vi.fn();

vi.mock('../../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/api')>();
  return {
    ...actual,
    JobsAPI: {
      ...actual.JobsAPI,
      create: (...args: unknown[]) => mockCreate(...args),
    },
    ImagesAPI: {
      ...actual.ImagesAPI,
      listCatalogSimilarityGroups: (...args: unknown[]) => mockListCatalogSimilarityGroups(...args),
    },
  };
});

vi.stubGlobal('fetch', mockFetch);

function renderCatalogCacheTab(props: { onOpenJobQueue?: () => void } = {}) {
  return render(
    <MemoryRouter>
      <Suspense fallback={null}>
        <CatalogCacheTab {...props} />
      </Suspense>
    </MemoryRouter>,
  );
}

describe('CatalogCacheTab', () => {
  beforeEach(() => {
    deleteMatching(() => true);
    mockCreate.mockReset();
    mockFetch.mockReset();
    mockListCatalogSimilarityGroups.mockReset();
    mockListCatalogSimilarityGroups.mockResolvedValue({ items: [], total: 0 });
    mockFetch.mockImplementation((input: RequestInfo | URL) => {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof Request
            ? input.url
            : String(input);
      if (url.includes('/cache/status')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            total_images: 10,
            cached_images: 5,
            missing: 5,
            cache_size_mb: 100,
            cache_dir: '/tmp/cache',
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled fetch in test: ${url}`));
    });
  });

  it('renders primary Build catalog cache CTA', async () => {
    renderCatalogCacheTab();
    expect(await screen.findByRole('button', { name: CATALOG_CACHE_BUILD_CTA })).toBeTruthy();
  });

  it('enqueues catalog_cache_build from primary CTA', async () => {
    mockCreate.mockResolvedValue({ id: 'job-chain', type: 'catalog_cache_build' });
    renderCatalogCacheTab();
    fireEvent.click(await screen.findByRole('button', { name: CATALOG_CACHE_BUILD_CTA }));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('catalog_cache_build', expect.anything());
    });
  });

  it('shows success copy and Open Job Queue after chain enqueue', async () => {
    mockCreate.mockResolvedValue({ id: 'job-chain', type: 'catalog_cache_build' });
    renderCatalogCacheTab();
    fireEvent.click(await screen.findByRole('button', { name: CATALOG_CACHE_BUILD_CTA }));
    expect(await screen.findByText(CATALOG_CACHE_BUILD_SUCCESS)).toBeTruthy();
    expect(screen.getByRole('button', { name: PROCESSING_OPEN_JOB_QUEUE })).toBeTruthy();
  });

  it('queue action invokes onOpenJobQueue or targets jobs route', async () => {
    mockCreate.mockResolvedValue({ id: 'job-chain', type: 'catalog_cache_build' });
    const onOpenJobQueue = vi.fn();
    renderCatalogCacheTab({ onOpenJobQueue });
    fireEvent.click(await screen.findByRole('button', { name: CATALOG_CACHE_BUILD_CTA }));
    const queueButton = await screen.findByRole('button', { name: PROCESSING_OPEN_JOB_QUEUE });
    fireEvent.click(queueButton);
    expect(onOpenJobQueue).toHaveBeenCalledTimes(1);
    expect(PROCESSING_JOB_QUEUE_ROUTE).toBe('/processing?tab=jobs');
  });

  it('reveals pipeline disclosure when toggled (no matching controls)', async () => {
    renderCatalogCacheTab();
    fireEvent.click(
      await screen.findByRole('button', { name: new RegExp(CATALOG_CACHE_PIPELINE_TITLE, 'i') }),
    );
    expect(await screen.findByRole('button', { name: CATALOG_CACHE_EMBED_CATALOG_LABEL })).toBeTruthy();
  });

  it('does not render matching-only controls (provider, weights, advanced options)', async () => {
    renderCatalogCacheTab();
    await screen.findByRole('button', { name: CATALOG_CACHE_BUILD_CTA });
    fireEvent.click(
      await screen.findByRole('button', { name: new RegExp(CATALOG_CACHE_PIPELINE_TITLE, 'i') }),
    );
    await screen.findByRole('button', { name: CATALOG_CACHE_EMBED_CATALOG_LABEL });
    expect(screen.queryByText(ADVANCED_OPTIONS_TITLE)).toBeNull();
    expect(screen.queryByText(ADVANCED_WEIGHTS_TITLE)).toBeNull();
    expect(screen.queryByLabelText(/provider/i)).toBeNull();
    expect(screen.queryByLabelText(/threshold/i)).toBeNull();
  });

  it('fetches catalog similarity groups preview and renders group summary', async () => {
    mockListCatalogSimilarityGroups.mockResolvedValue({
      items: [
        {
          group_id: 7,
          seed: {
            id: 1,
            key: 'seed-key',
            filename: 's.jpg',
            filepath: '/tmp/s.jpg',
            date_taken: '2024-01-01',
            rating: 5,
            pick: false,
            color_label: '',
            keywords: [],
            title: '',
            caption: '',
            copyright: '',
            width: 100,
            height: 100,
            instagram_posted: false,
          },
          candidates: [
            {
              id: 2,
              key: 'cand-key',
              filename: 'c.jpg',
              filepath: '/tmp/c.jpg',
              date_taken: '2024-01-02',
              rating: 5,
              pick: false,
              color_label: '',
              keywords: [],
              title: '',
              caption: '',
              copyright: '',
              width: 100,
              height: 100,
              instagram_posted: false,
              similarity: 0.91,
            },
          ],
          candidate_count: 1,
          best_similarity: 0.91,
        },
      ],
      total: 22,
    });
    renderCatalogCacheTab();
    await waitFor(() => {
      expect(mockListCatalogSimilarityGroups).toHaveBeenCalledWith({ limit: 12, offset: 0 });
    });
    expect(await screen.findByText(CATALOG_CACHE_SIMILARITY_PREVIEW_TITLE)).toBeTruthy();
    expect(screen.getByText(CATALOG_CACHE_SIMILARITY_BEST_MATCH_PCT(91))).toBeTruthy();
    expect(screen.getByText(CATALOG_CACHE_SIMILARITY_TOTAL_GROUPS_LABEL(22))).toBeTruthy();
    expect(screen.getByRole('link', { name: 'View all' })).toHaveAttribute(
      'href',
      PROCESSING_JOB_QUEUE_ROUTE,
    );
  });

  it('enqueues batch_embed_image catalog-only from pipeline section', async () => {
    mockCreate.mockResolvedValue({ id: 'job-embed', type: 'batch_embed_image' });
    renderCatalogCacheTab();
    fireEvent.click(
      await screen.findByRole('button', { name: new RegExp(CATALOG_CACHE_PIPELINE_TITLE, 'i') }),
    );
    fireEvent.click(await screen.findByRole('button', { name: CATALOG_CACHE_EMBED_CATALOG_LABEL }));
    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith('batch_embed_image', { image_type: 'catalog' });
    });
  });
});
