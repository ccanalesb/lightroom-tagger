import { Suspense, useState } from 'react';
import type { DescriptionItem, ImageDescription } from '../../services/api';
import type { Resource } from '../../utils/createResource';
import { DescriptionPanel } from '../DescriptionPanel';
import { ImageTypeBadge } from '../ui/badges';
import { GenerateButton } from '../ui/description-atoms';
import { formatDate } from '../../utils/date';
import {
  DESC_PAGE_NO_DESCRIPTION,
  DESC_PAGE_GENERATE,
  DESC_PAGE_GENERATING,
  DESC_PAGE_SOURCE_CATALOG,
  DESC_PAGE_SOURCE_INSTAGRAM,
  MSG_LOADING,
  MODAL_CLOSE,
} from '../../constants/strings';

export interface DescriptionDetailModalProps {
  item: DescriptionItem;
  descriptionResource: Resource<{ description: ImageDescription | null }> | null;
  imageUrl: string;
  thumbnailUrl: string;
  generating: boolean;
  onGenerate: (e?: React.MouseEvent) => void;
  onClose: () => void;
}

export function DescriptionDetailModal({
  item, descriptionResource, imageUrl, thumbnailUrl, generating, onGenerate, onClose,
}: DescriptionDetailModalProps) {
  const [imgSrc, setImgSrc] = useState(imageUrl);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center overflow-y-auto p-4 pt-12" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <ImageTypeBadge type={item.image_type} />
            <h3 className="text-lg font-semibold text-gray-900">{item.filename || item.image_key}</h3>
          </div>
          <div className="flex items-center gap-2">
            <GenerateButton
              hasDescription={!!item.has_description}
              generating={generating}
              onClick={onGenerate}
            />
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none px-1">&times;</button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6">
          <div className="bg-gray-100 rounded-lg overflow-hidden flex items-center justify-center min-h-[300px]">
            <img
              src={imgSrc}
              alt={item.filename || item.image_key}
              className="max-w-full max-h-[500px] object-contain"
              onError={() => setImgSrc(thumbnailUrl)}
            />
          </div>

          <div className="overflow-y-auto max-h-[500px]">
            {descriptionResource ? (
              <Suspense fallback={<p className="text-gray-400 text-sm">{MSG_LOADING}</p>}>
                <DescriptionContent resource={descriptionResource} generating={generating} onGenerate={onGenerate} />
              </Suspense>
            ) : (
              <NoDescription generating={generating} onGenerate={onGenerate} />
            )}
          </div>
        </div>

        <div className="px-6 py-3 border-t flex justify-between items-center text-xs text-gray-400">
          <span>
            {item.image_type === 'catalog' ? DESC_PAGE_SOURCE_CATALOG : DESC_PAGE_SOURCE_INSTAGRAM}
            {item.desc_model && ` · model: ${item.desc_model}`}
            {item.described_at && ` · ${formatDate(item.described_at)}`}
          </span>
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">
            {MODAL_CLOSE}
          </button>
        </div>
      </div>
    </div>
  );
}

function DescriptionContent({
  resource, generating, onGenerate,
}: {
  resource: Resource<{ description: ImageDescription | null }>;
  generating: boolean;
  onGenerate: (e?: React.MouseEvent) => void;
}) {
  const { description } = resource.read();
  if (description) return <DescriptionPanel description={description} />;
  return <NoDescription generating={generating} onGenerate={onGenerate} />;
}

function NoDescription({ generating, onGenerate }: { generating: boolean; onGenerate: (e?: React.MouseEvent) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-400">
      <p className="text-sm italic">{DESC_PAGE_NO_DESCRIPTION}</p>
      <button
        type="button"
        onClick={onGenerate}
        disabled={generating}
        className="px-4 py-2 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
      >
        {generating ? DESC_PAGE_GENERATING : DESC_PAGE_GENERATE}
      </button>
    </div>
  );
}
