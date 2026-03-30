import type { DescriptionListResult } from '../../services/api';
import type { Resource } from '../../utils/createResource';

export function TotalCount({ resource }: { resource: Resource<DescriptionListResult> }) {
  const { total } = resource.read();
  return <span className="ml-auto self-center text-xs text-gray-400">{total} images</span>;
}
