import type { DescriptionItem } from '../../services/api';
import { DESC_PAGE_NO_DESCRIPTION } from '../../constants/strings';
import { ImageTypeBadge } from '../ui/badges';
import { AsyncThumbnail } from '../ui/AsyncThumbnail';
import { GenerateButton, DescriptionMeta } from '../ui/description-atoms';

export interface DescriptionCardProps {
  item: DescriptionItem;
  thumbnailUrl: string;
  generating: boolean;
  onGenerate: (e?: React.MouseEvent) => void;
  onClick: () => void;
}

export function DescriptionCard({ item, thumbnailUrl, generating, onGenerate, onClick }: DescriptionCardProps) {
  return (
    <div
      className="flex gap-4 border rounded-lg bg-white p-3 hover:shadow-sm transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <AsyncThumbnail
        src={thumbnailUrl}
        alt={item.filename || item.image_key}
        className="w-20 h-20 flex-shrink-0 rounded overflow-hidden"
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ImageTypeBadge type={item.image_type} />
              <p className="text-sm font-medium text-gray-900 truncate">
                {item.filename || item.image_key}
              </p>
            </div>
            {item.has_description ? (
              <p className="text-sm text-gray-600 mt-1 line-clamp-2">{item.summary}</p>
            ) : (
              <p className="text-sm text-gray-400 italic mt-1">{DESC_PAGE_NO_DESCRIPTION}</p>
            )}
          </div>

          <GenerateButton
            hasDescription={!!item.has_description}
            generating={generating}
            onClick={onGenerate}
          />
        </div>

        <DescriptionMeta
          bestPerspective={item.best_perspective}
          imageType={item.image_type}
          hasDescription={!!item.has_description}
          model={item.desc_model}
          describedAt={item.described_at}
          dateRef={item.date_ref}
        />
      </div>
    </div>
  );
}
