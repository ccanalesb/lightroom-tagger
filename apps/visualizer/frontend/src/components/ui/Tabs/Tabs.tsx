import { type ReactElement, type ReactNode } from 'react';

export interface Tab {
  id: string;
  label: string;
  content: ReactNode;
}

export type TabNavItem = { id: string; label: string };

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

export function TabNav(props: {
  tabs: TabNavItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}): ReactElement {
  const { tabs, activeTab, onTabChange, className = '' } = props;
  return (
    <div className={`border-b border-border${className ? ` ${className}` : ''}`.trim()}>
      <nav className="flex space-x-1 overflow-x-auto" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            onClick={() => onTabChange(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`
                px-4 py-2 text-sm font-semibold whitespace-nowrap
                border-b-[3px] transition-all duration-150
                ${
                  activeTab === tab.id
                    ? 'border-accent text-accent'
                    : 'border-transparent text-text opacity-60 hover:text-text hover:opacity-100 hover:border-border-strong'
                }
              `.trim()}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

export function Tabs({ tabs, activeTab, onTabChange, className = '' }: TabsProps) {
  return (
    <div className={className}>
      <TabNav
        tabs={tabs.map((t) => ({ id: t.id, label: t.label }))}
        activeTab={activeTab}
        onTabChange={onTabChange}
      />

      {/* Tab content */}
      <div className="mt-6">
        {tabs.find((tab) => tab.id === activeTab)?.content}
      </div>
    </div>
  );
}
