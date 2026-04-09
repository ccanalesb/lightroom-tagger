import { useState } from 'react';
import { Tabs, Tab } from '../components/ui/Tabs';
import { MatchingTab } from '../components/processing/MatchingTab';
import { DescriptionsTab } from '../components/processing/DescriptionsTab';
import { JobQueueTab } from '../components/processing/JobQueueTab';
import { ProvidersTab } from '../components/processing/ProvidersTab';
import {
  TAB_VISION_MATCHING,
  TAB_DESCRIPTIONS,
  TAB_JOB_QUEUE,
  TAB_PROVIDERS,
  NAV_PROCESSING,
} from '../constants/strings';

export function ProcessingPage() {
  const [activeTab, setActiveTab] = useState('matching');

  const tabs: Tab[] = [
    { id: 'matching', label: TAB_VISION_MATCHING, content: <MatchingTab /> },
    { id: 'descriptions', label: TAB_DESCRIPTIONS, content: <DescriptionsTab /> },
    { id: 'jobs', label: TAB_JOB_QUEUE, content: <JobQueueTab /> },
    { id: 'providers', label: TAB_PROVIDERS, content: <ProvidersTab /> },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">{NAV_PROCESSING}</h1>
        <p className="text-text-secondary">
          AI-powered vision matching, description generation, and job monitoring
        </p>
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
