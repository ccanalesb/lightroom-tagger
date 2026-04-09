import { Card, CardContent } from '../ui/Card';
import { TAB_MATCHES, PLACEHOLDER_MATCHES_VIEW } from '../../constants/strings';

export function MatchesTab() {
  return (
    <div className="space-y-6">
      <Card padding="lg">
        <CardContent>
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-text">{TAB_MATCHES}</h3>
            <p className="mt-1 text-sm text-text-secondary">
              {PLACEHOLDER_MATCHES_VIEW}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
