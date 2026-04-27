import type { ReactNode } from 'react';

export interface CollapsibleSectionProps {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}

/**
 * Disclosure shell shared by Advanced sections that don't depend on matching state.
 * The visual chrome mirrors `matching/AdvancedOptions.tsx` so toggles look the same
 * across tabs, but no provider/threshold/weights props leak in.
 */
export function CollapsibleSection({ title, isOpen, onToggle, children }: CollapsibleSectionProps) {
  return (
    <div className="border-t pt-4">
      <button
        onClick={onToggle}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {isOpen ? '▼' : '▶'} {title}
      </button>

      {isOpen && (
        <div className="mt-4 space-y-4 bg-white p-4 rounded border">
          {children}
        </div>
      )}
    </div>
  );
}
