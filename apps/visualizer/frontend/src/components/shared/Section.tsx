import type { ReactNode } from 'react';

interface SectionProps {
  title: string;
  children: ReactNode;
}

export function Section({ title, children }: SectionProps) {
  return (
    <div>
      <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{title}</h5>
      {children}
    </div>
  );
}
