import type { DescriptionItem, DescriptionListResult } from '../../services/api';
import type { Resource } from '../../utils/createResource';
import { DescriptionCard } from './DescriptionCard';
import {
  DESC_PAGE_EMPTY,
  PAGINATION_PREVIOUS,
  PAGINATION_NEXT,
} from '../../constants/strings';

export interface DescriptionGridProps {
  resource: Resource<DescriptionListResult>;
  page: number;
  limit: number;
  generatingKeys: Set<string>;
  thumbnailUrl: (item: DescriptionItem) => string;
  onGenerate: (item: DescriptionItem, e?: React.MouseEvent) => void;
  onOpenModal: (item: DescriptionItem) => void;
  onPageChange: (page: number) => void;
}

export function DescriptionGrid({
  resource, page, limit, generatingKeys, thumbnailUrl, onGenerate, onOpenModal, onPageChange,
}: DescriptionGridProps) {
  const { items, total } = resource.read();
  const totalPages = Math.ceil(total / limit) || 1;

  if (items.length === 0) {
    return <p className="text-gray-500 text-center py-12">{DESC_PAGE_EMPTY}</p>;
  }

  return (
    <>
      <div className="space-y-3">
        {items.map(item => (
          <DescriptionCard
            key={`${item.image_type}-${item.image_key}`}
            item={item}
            thumbnailUrl={thumbnailUrl(item)}
            generating={generatingKeys.has(item.image_key)}
            onGenerate={(e) => onGenerate(item, e)}
            onClick={() => onOpenModal(item)}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 pt-4">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-3 py-1 rounded text-sm border disabled:opacity-30"
          >
            {PAGINATION_PREVIOUS}
          </button>
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1 rounded text-sm border disabled:opacity-30"
          >
            {PAGINATION_NEXT}
          </button>
        </div>
      )}
    </>
  );
}
