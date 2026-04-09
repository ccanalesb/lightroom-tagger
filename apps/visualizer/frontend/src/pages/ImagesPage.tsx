import { useState } from 'react';
import { Tabs, Tab } from '../components/ui/Tabs';
import { InstagramTab } from '../components/images/InstagramTab';
import { CatalogTab } from '../components/images/CatalogTab';
import { MatchesTab } from '../components/images/MatchesTab';
import { TAB_INSTAGRAM, TAB_CATALOG, TAB_MATCHES } from '../constants/strings';

export function ImagesPage() {
  const [activeTab, setActiveTab] = useState('instagram');

  const tabs: Tab[] = [
    { id: 'instagram', label: TAB_INSTAGRAM, content: <InstagramTab /> },
    { id: 'catalog', label: TAB_CATALOG, content: <CatalogTab /> },
    { id: 'matches', label: TAB_MATCHES, content: <MatchesTab /> },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-section text-text mb-2">Images</h1>
        <p className="text-text-secondary">
          Browse Instagram photos, catalog images, and review matched pairs
        </p>
      </div>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}
