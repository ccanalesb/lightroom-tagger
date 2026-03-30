interface StatusBadgeOptions {
  withBorder?: boolean
}

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  completed: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200' },
  failed:    { bg: 'bg-red-100',   text: 'text-red-800',   border: 'border-red-200'   },
  running:   { bg: 'bg-blue-100',  text: 'text-blue-800',  border: 'border-blue-200'  },
  cancelled: { bg: 'bg-gray-100',  text: 'text-gray-800',  border: 'border-gray-200'  },
}

const DEFAULT_COLOR = { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-200' }

export function statusBadgeClasses(status: string, opts: StatusBadgeOptions = {}): string {
  const c = STATUS_COLORS[status] ?? DEFAULT_COLOR
  const parts = [c.bg, c.text]
  if (opts.withBorder) parts.push(c.border)
  return parts.join(' ')
}

const PROGRESS_COLORS: Record<string, string> = {
  completed: 'bg-green-500',
  failed:    'bg-red-500',
  running:   'bg-blue-500',
}

export function progressBarColor(status: string): string {
  return PROGRESS_COLORS[status] ?? 'bg-gray-400'
}
