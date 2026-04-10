import { useEffect } from 'react';
import type { CatalogImage } from '../../services/api';
import { Badge } from '../ui/Badge';
import { MetadataRow } from '../ui/MetadataRow';
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
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

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
          </div>
        </div>
      </div>
    </div>
  );
}
