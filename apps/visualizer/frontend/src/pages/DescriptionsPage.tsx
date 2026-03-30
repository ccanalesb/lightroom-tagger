import { Suspense, useEffect, useMemo, useState } from 'react';
import type { DescriptionItem, ImageDescription, Job } from '../services/api';
import { DescriptionsAPI, JobsAPI } from '../services/api';
import { BatchActionPanel } from '../components/descriptions/BatchActionPanel';
import { DescriptionDetailModal } from '../components/descriptions/DescriptionDetailModal';
import { DescriptionGrid } from '../components/descriptions/DescriptionGrid';
import { TotalCount } from '../components/descriptions/TotalCount';
import { useMatchOptions } from '../stores/matchOptionsContext';
import { createResource, type Resource } from '../utils/createResource';
import { thumbnailUrl as buildThumbUrl, fullImageUrl as buildFullUrl } from '../utils/imageUrl';
import {
  DESC_PAGE_TITLE,
  DESC_PAGE_TAB_ALL,
  DESC_PAGE_TAB_CATALOG,
  DESC_PAGE_TAB_INSTAGRAM,
  DESC_PAGE_BATCH_ALL,
  DESC_PAGE_BATCH_CATALOG,
  DESC_PAGE_BATCH_INSTAGRAM,
  MSG_LOADING,
  ITEMS_PER_PAGE,
  MSG_FAILED_START_JOB,
} from '../constants/strings';

type TabValue = 'all' | 'catalog' | 'instagram';

const TABS: { value: TabValue; label: string }[] = [
  { value: 'all', label: DESC_PAGE_TAB_ALL },
  { value: 'catalog', label: DESC_PAGE_TAB_CATALOG },
  { value: 'instagram', label: DESC_PAGE_TAB_INSTAGRAM },
];

const BATCH_LABELS: Record<TabValue, string> = {
  all: DESC_PAGE_BATCH_ALL,
  catalog: DESC_PAGE_BATCH_CATALOG,
  instagram: DESC_PAGE_BATCH_INSTAGRAM,
};

export function DescriptionsPage() {
  const { availableModels } = useMatchOptions();

  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<TabValue>('all');
  const [dateFilter, setDateFilter] = useState<'all' | '3months' | '6months'>('all');
  const [force, setForce] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchJob, setBatchJob] = useState<Job | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [generatingKeys, setGeneratingKeys] = useState<Set<string>>(new Set());
  const [modalItem, setModalItem] = useState<DescriptionItem | null>(null);
  const [modalDescResource, setModalDescResource] = useState<Resource<{ description: ImageDescription | null }> | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!selectedModel && availableModels.length > 0) {
      const def = availableModels.find(m => m.default) ?? availableModels[0];
      if (def) setSelectedModel(def.name);
    }
  }, [availableModels, selectedModel]);

  const limit = ITEMS_PER_PAGE;

  const gridResource = useMemo(
    () => createResource(
      DescriptionsAPI.list({
        image_type: tab === 'all' ? undefined : tab,
        limit,
        offset: (page - 1) * limit,
      })
    ),
    [tab, page, limit, refreshKey],
  );

  useEffect(() => { setPage(1); }, [tab]);

  async function handleBatchDescribe() {
    setBatchRunning(true);
    setBatchJob(null);
    setBatchError(null);
    try {
      const job = await JobsAPI.create('batch_describe', {
        image_type: tab === 'all' ? 'both' : tab,
        date_filter: dateFilter,
        force,
        vision_model: selectedModel || undefined,
      });
      setBatchJob(job);
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : MSG_FAILED_START_JOB);
    } finally {
      setBatchRunning(false);
    }
  }

  async function handleGenerate(item: DescriptionItem, e?: React.MouseEvent) {
    e?.stopPropagation();
    setGeneratingKeys(prev => new Set(prev).add(item.image_key));
    try {
      const res = await DescriptionsAPI.generate(
        item.image_key,
        item.image_type,
        force,
        selectedModel || undefined,
      );
      if (res.description) {
        setRefreshKey(prev => prev + 1);
        if (modalItem?.image_key === item.image_key) {
          setModalDescResource(createResource(Promise.resolve({ description: res.description as ImageDescription })));
        }
      }
    } finally {
      setGeneratingKeys(prev => { const next = new Set(prev); next.delete(item.image_key); return next; });
    }
  }

  function openModal(item: DescriptionItem) {
    setModalItem(item);
    setModalDescResource(
      item.has_description
        ? createResource(DescriptionsAPI.get(item.image_key))
        : null,
    );
  }

  function closeModal() {
    setModalItem(null);
    setModalDescResource(null);
  }

  const thumbnailUrl = (item: DescriptionItem) =>
    buildThumbUrl(item.image_type, item.image_key);

  const fullImageUrl = (item: DescriptionItem) =>
    buildFullUrl(item.image_type, item.image_key);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">{DESC_PAGE_TITLE}</h2>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {TABS.map(t => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.value
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
        <Suspense fallback={<span className="ml-auto self-center text-xs text-gray-400">…</span>}>
          <TotalCount resource={gridResource} />
        </Suspense>
      </div>

      <BatchActionPanel
        availableModels={availableModels}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        dateFilter={dateFilter}
        onDateFilterChange={setDateFilter}
        force={force}
        onForceChange={setForce}
        batchRunning={batchRunning}
        batchLabel={BATCH_LABELS[tab]}
        onBatchDescribe={handleBatchDescribe}
        batchJob={batchJob}
        onDismissJob={() => setBatchJob(null)}
        batchError={batchError}
        onDismissError={() => setBatchError(null)}
      />

      <Suspense fallback={<p className="text-gray-500 text-center py-12">{MSG_LOADING}</p>}>
        <DescriptionGrid
          resource={gridResource}
          page={page}
          limit={limit}
          generatingKeys={generatingKeys}
          thumbnailUrl={thumbnailUrl}
          onGenerate={handleGenerate}
          onOpenModal={openModal}
          onPageChange={setPage}
        />
      </Suspense>

      {modalItem && (
        <DescriptionDetailModal
          item={modalItem}
          descriptionResource={modalDescResource}
          imageUrl={fullImageUrl(modalItem)}
          thumbnailUrl={thumbnailUrl(modalItem)}
          generating={generatingKeys.has(modalItem.image_key)}
          onGenerate={(e) => handleGenerate(modalItem, e)}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
