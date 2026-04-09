import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingClasses = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};

export function Card({
  children,
  className = '',
  onClick,
  hoverable = false,
  padding = 'md',
}: CardProps) {
  return (
    <div
      className={`
        bg-bg border border-border rounded-card
        shadow-card transition-all duration-150
        ${paddingClasses[padding]}
        ${hoverable || onClick ? 'hover:shadow-deep hover:border-border-strong cursor-pointer' : ''}
        ${className}
      `.trim()}
      onClick={onClick}
      style={{ backgroundColor: 'var(--color-background)' }}
    >
      {children}
    </div>
  );
}
