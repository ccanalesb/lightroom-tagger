import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, fullWidth = false, className = '', ...props }, ref) => {
    return (
      <div className={fullWidth ? 'w-full' : ''}>
        {label && (
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            px-3 py-2 rounded-base border border-border
            bg-bg text-text placeholder-text-tertiary
            focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent
            hover:border-border-strong
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150
            ${fullWidth ? 'w-full' : ''}
            ${error ? 'border-error focus:ring-error' : ''}
            ${className}
          `.trim()}
          {...props}
        />
        {error && (
          <p className="mt-1 text-sm text-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
