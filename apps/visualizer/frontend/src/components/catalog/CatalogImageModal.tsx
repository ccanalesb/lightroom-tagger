import { useCallback, useEffect, useState } from 'react';
import type { CatalogImage, ImageDescription } from '../../services/api';
import { DescriptionsAPI, JobsAPI, ProvidersAPI } from '../../services/api';
import type { Job } from '../../types/job';
import { DescriptionPanel } from '../DescriptionPanel/DescriptionPanel';
import { GenerateButton } from '../ui/description-atoms/GenerateButton';
import { ProviderModelSelect } from '../ui/ProviderModelSelect';
import { Badge } from '../ui/Badge';
import { MetadataRow } from '../ui/MetadataRow';
import { useJobSocket } from '../../hooks/useJobSocket';
import {
  IMAGE_DETAILS_TITLE,
  LABEL_FILENAME,
  LABEL_DATE,
  DATE_NO_DATE,
} from '../../constants/strings';

interface CatalogImageModalProps {
  image: CatalogImage;
  onClose: () => void;
}

export function CatalogImageModal({ image, onClose }: CatalogImageModalProps) {
  const [description, setDescription] = useState<ImageDescription | null>(null);
  const [loadingDesc, setLoadingDesc] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [descError, setDescError] = useState<string | null>(null);
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);
  const [descProviderId, setDescProviderId] = useState<string | null>(null);
  const [descModelId, setDescModelId] = useState<string | null>(null);
  const [showModelOptions, setShowModelOptions] = useState(false);

  useEffect(() => {
    ProvidersAPI.getDefaults()
      .then((defaults) => {
        const d = defaults.description;
        if (d?.provider) setDescProviderId(d.provider);
        if (d?.model) setDescModelId(d.model);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoadingDesc(true);
    setDescError(null);
    setDescription(null);

    DescriptionsAPI.get(image.key)
      .then((data) => {
        if (!cancelled) {
          setDescription(data.description);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDescError(String(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingDesc(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [image.key]);

  const refreshDescription = useCallback(() => {
    DescriptionsAPI.get(image.key)
      .then((data) => setDescription(data.description))
      .catch(() => {});
  }, [image.key]);

  useJobSocket({
    onJobUpdated: useCallback(
      (job: Job) => {
        if (!pendingJobId || job.id !== pendingJobId) return;
        if (job.status === 'completed') {
          setPendingJobId(null);
          setGenerating(false);
          refreshDescription();
        } else if (job.status === 'failed') {
          setPendingJobId(null);
          setGenerating(false);
          setDescError(job.error ?? 'Description generation failed');
        } else if (job.status === 'cancelled') {
          setPendingJobId(null);
          setGenerating(false);
        }
      },
      [pendingJobId, refreshDescription],
    ),
  });

  const handleGenerateDescription = useCallback(async () => {
    setGenerating(true);
    setDescError(null);
    try {
      const job = await JobsAPI.create('single_describe', {
        image_key: image.key,
        image_type: 'catalog',
        force: false,
        ...(descProviderId && { provider_id: descProviderId }),
        ...(descModelId && { provider_model: descModelId }),
      });
      setPendingJobId(job.id);
    } catch (err) {
      setDescError(String(err));
      setGenerating(false);
    }
  }, [image.key, descProviderId, descModelId]);

  const dateDisplay = image.date_taken
    ? new Date(image.date_taken).toLocaleString()
    : DATE_NO_DATE;

  const keywords = Array.isArray(image.keywords) ? image.keywords : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[90vh] bg-bg rounded-card shadow-deep overflow-hidden"
        style={{ backgroundColor: 'var(--color-background)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 rounded-base bg-surface/80 backdrop-blur-sm border border-border hover:bg-surface-hover transition-all"
        >
          <svg className="w-5 h-5 text-text" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="grid md:grid-cols-2 gap-6 p-6 overflow-y-auto max-h-[90vh]">
          <div className="aspect-square bg-surface rounded-base overflow-hidden">
            <img
              src={`/api/images/catalog/${encodeURIComponent(image.key)}/thumbnail`}
              alt={image.filename}
              className="w-full h-full object-contain"
            />
          </div>

          <div className="space-y-6">
            <div>
              <h2 className="text-card-title text-text mb-2">{IMAGE_DETAILS_TITLE}</h2>
              <div className="flex flex-wrap gap-2">
                {image.instagram_posted && <Badge variant="success">Posted to Instagram</Badge>}
                {description && (description.summary || description.best_perspective) && (
                  <Badge variant="accent">AI</Badge>
                )}
                {image.rating > 0 && <Badge variant="accent">{image.rating} Stars</Badge>}
                {image.pick && <Badge variant="accent">Pick</Badge>}
                {image.color_label && <Badge variant="default">{image.color_label}</Badge>}
              </div>
            </div>

            <div className="space-y-3">
              <MetadataRow label={LABEL_FILENAME} value={image.filename} />
              {image.title && <MetadataRow label="Title" value={image.title} />}
              <MetadataRow label={LABEL_DATE} value={dateDisplay} />
              {image.filepath && <MetadataRow label="Path" value={image.filepath} mono />}
              {image.width && image.height && (
                <MetadataRow label="Dimensions" value={`${image.width} × ${image.height}`} />
              )}
            </div>

            {image.caption && (
              <div className="p-4 bg-surface rounded-base border border-border">
                <h3 className="text-sm font-medium text-text mb-2">Caption</h3>
                <p className="text-sm text-text-secondary">{image.caption}</p>
              </div>
            )}

            {keywords.length > 0 && (
              <div className="p-4 bg-surface rounded-base border border-border">
                <h3 className="text-sm font-medium text-text mb-2">Keywords</h3>
                <div className="flex flex-wrap gap-2">
                  {keywords.map((keyword, idx) => (
                    <Badge key={idx} variant="default">{keyword}</Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="p-4 bg-surface rounded-base border border-border">
              <h3 className="text-sm font-medium text-text mb-2">AI description</h3>
              {loadingDesc && (
                <p className="text-sm text-text-tertiary">Loading description…</p>
              )}
              {descError && <p className="text-sm text-error">{descError}</p>}
              {generating && (
                <div className="flex items-center gap-2 py-2">
                  <svg className="animate-spin h-4 w-4 text-accent" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-sm text-text-secondary">Generating description…</span>
                </div>
              )}
              <DescriptionPanel description={description} compact />
              <div className="mt-3 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowModelOptions(!showModelOptions)}
                  className="text-xs text-text-tertiary hover:text-text-secondary transition-colors"
                >
                  {showModelOptions ? 'Hide options' : 'Model options'}
                </button>
                <GenerateButton
                  hasDescription={Boolean(description?.summary)}
                  generating={generating}
                  onClick={() => {
                    void handleGenerateDescription();
                  }}
                />
              </div>
              {showModelOptions && (
                <ProviderModelSelect
                  providerId={descProviderId}
                  modelId={descModelId}
                  onChange={(pid, mid) => { setDescProviderId(pid); setDescModelId(mid); }}
                  className="mt-3"
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
