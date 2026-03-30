import type { DescriptionItem, DescriptionListResult } from '../../services/api';
import type { Resource } from '../../utils/createResource';
import { DescriptionCard } from './DescriptionCard';
import { Pagination } from '../ui/Pagination';
import { DESC_PAGE_EMPTY } from '../../constants/strings';

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

      <Pagination currentPage={page} totalPages={totalPages} onPageChange={onPageChange} />
    </>
  );
}
