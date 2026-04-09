import { Card, CardContent } from '../ui/Card';
import { TAB_CATALOG, PLACEHOLDER_CATALOG_VIEW } from '../../constants/strings';

export function CatalogTab() {
  return (
    <div className="space-y-6">
      <Card padding="lg">
        <CardContent>
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">{TAB_CATALOG}</h3>
            <p className="mt-1 text-sm text-text-secondary">
              {PLACEHOLDER_CATALOG_VIEW}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
