import type { DescriptionListResult } from '../../services/api';
import type { Resource } from '../../utils/createResource';

import { LABEL_IMAGES } from '../../constants/strings';

export function TotalCount({ resource }: { resource: Resource<DescriptionListResult> }) {
  const { total } = resource.read();
  return <span className="ml-auto self-center text-xs text-gray-400">{total} {LABEL_IMAGES}</span>;
}
