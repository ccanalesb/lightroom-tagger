import { useEffect } from 'react';
import type { InstagramImage } from '../../services/api';
import { Badge } from '../ui/Badge';
import { MetadataRow } from '../ui/MetadataRow';
import {
  IMAGE_DETAILS_TITLE,
  IMAGE_DETAILS_AI_DESCRIPTION,
  BADGE_MATCHED,
  BADGE_DESCRIBED,
  BADGE_PROCESSED,
  LABEL_FILENAME,
  LABEL_FOLDER,
  LABEL_SOURCE,
  LABEL_DATE,
  LABEL_IMAGE_HASH_DISPLAY,
  LABEL_CATALOG_MATCH,
  DATE_NO_DATE,
  DATE_ESTIMATED_SUFFIX,
} from '../../constants/strings';
interface ImageDetailsModalProps {
  image: InstagramImage;
  onClose: () => void;
}

export function ImageDetailsModal({ image, onClose }: ImageDetailsModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  const dateDisplay = image.created_at
    ? new Date(image.created_at).toLocaleString()
    : image.date_folder
      ? `${image.date_folder.slice(0, 4)}/${image.date_folder.slice(4, 6)} ${DATE_ESTIMATED_SUFFIX}`
      : DATE_NO_DATE;

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
              src={`/api/images/instagram/${encodeURIComponent(image.key)}/thumbnail`}
              alt={image.filename}
              className="w-full h-full object-contain"
            />
          </div>

          <div className="space-y-6">
            <div>
              <h2 className="text-card-title text-text mb-2">{IMAGE_DETAILS_TITLE}</h2>
              <div className="flex flex-wrap gap-2">
                {image.matched_catalog_key && <Badge variant="success">{BADGE_MATCHED}</Badge>}
                {image.description && <Badge variant="accent">{BADGE_DESCRIBED}</Badge>}
                {image.processed && <Badge variant="default">{BADGE_PROCESSED}</Badge>}
              </div>
            </div>

            <div className="space-y-3">
              <MetadataRow label={LABEL_FILENAME} value={image.filename} />
              <MetadataRow label={LABEL_FOLDER} value={image.instagram_folder} />
              <MetadataRow label={LABEL_SOURCE} value={image.source_folder} />
              <MetadataRow label={LABEL_DATE} value={dateDisplay} />
              {image.image_hash && (
                <MetadataRow label={LABEL_IMAGE_HASH_DISPLAY} value={image.image_hash} mono />
              )}
              {image.matched_catalog_key && (
                <MetadataRow label={LABEL_CATALOG_MATCH} value={image.matched_catalog_key} mono />
              )}
            </div>

            {image.description && (
              <div className="p-4 bg-surface rounded-base border border-border">
                <h3 className="text-sm font-medium text-text mb-2">{IMAGE_DETAILS_AI_DESCRIPTION}</h3>
                <p className="text-sm text-text-secondary">{image.description}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
