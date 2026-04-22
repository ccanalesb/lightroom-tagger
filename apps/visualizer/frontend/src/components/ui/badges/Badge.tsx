import { ReactNode } from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'accent';

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-surface text-text-secondary border-border',
  success: 'bg-green-50 dark:bg-green-900/20 text-success border-green-200 dark:border-green-800',
  warning: 'bg-orange-50 dark:bg-orange-900/20 text-warning border-orange-200 dark:border-orange-800',
  error: 'bg-red-50 dark:bg-red-900/20 text-error border-red-200 dark:border-red-800',
  accent: 'bg-accent-light text-accent border-blue-200 dark:border-blue-800',
};

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold
        border ${variantClasses[variant]} ${className}
      `.trim()}
    >
      {children}
    </span>
  );
}
