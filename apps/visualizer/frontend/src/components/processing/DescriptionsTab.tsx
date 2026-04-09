import { useState, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { WorkerSlider } from '../matching/WorkerSlider';
import { JobsAPI } from '../../services/api';
import { ADVANCED_OPTIONS_TITLE } from '../../constants/strings';

export function DescriptionsTab() {
  const [maxWorkers, setMaxWorkers] = useState(2);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const startDescriptions = useCallback(async () => {
    setIsStarting(true);
    try {
      await JobsAPI.create('batch_describe', { max_workers: maxWorkers });
      alert('Description generation job started! Check Job Queue tab to monitor progress.');
    } catch (error) {
      alert(`Failed to start job: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsStarting(false);
    }
  }, [maxWorkers]);

  return (
    <div className="max-w-2xl">
      <Card padding="lg">
        <CardHeader>
          <CardTitle>Generate Image Descriptions</CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-6">
            <p className="text-sm text-text-secondary">
              AI-generated descriptions improve matching accuracy by providing semantic context.
            </p>

            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center space-x-2 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
              >
                <svg
                  className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                <span>{ADVANCED_OPTIONS_TITLE}</span>
              </button>
            </div>

            {showAdvanced && (
              <div className="pt-4 border-t border-border">
                <WorkerSlider value={maxWorkers} onChange={setMaxWorkers} />
              </div>
            )}

            <div className="pt-4">
              <Button variant="primary" size="lg" fullWidth onClick={startDescriptions} disabled={isStarting}>
                {isStarting ? 'Starting Job...' : 'Generate Descriptions'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
