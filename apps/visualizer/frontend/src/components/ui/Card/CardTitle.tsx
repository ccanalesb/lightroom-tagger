import { ReactNode } from 'react';

interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export function CardTitle({ children, className = '' }: CardTitleProps) {
  return (
    <h3 className={`text-card-title text-text font-bold ${className}`}>
      {children}
    </h3>
  );
}
