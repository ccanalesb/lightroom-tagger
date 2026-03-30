import type { ReactNode } from 'react'

export type AlertTone = 'success' | 'danger' | 'warning' | 'info'

const TONE_CLASSES: Record<AlertTone, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  danger:  'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  info:    'bg-blue-50 border-blue-200 text-blue-800',
}

interface AlertProps {
  tone: AlertTone
  message: string
  onDismiss?: () => void
  children?: ReactNode
}

export function Alert({ tone, message, onDismiss, children }: AlertProps) {
  return (
    <div className={`flex items-start gap-3 px-4 py-3 border rounded-lg text-sm ${TONE_CLASSES[tone]}`}>
      <div className="flex-1 min-w-0">
        <p className="font-medium">{message}</p>
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 opacity-60 hover:opacity-100"
        >
          &times;
        </button>
      )}
    </div>
  )
}
