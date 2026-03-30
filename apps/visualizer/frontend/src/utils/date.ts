type DateInput = string | null | undefined

export function formatDateTime(value: DateInput): string {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

export function formatDate(value: DateInput): string {
  if (!value) return ''
  return new Date(value).toLocaleDateString()
}

export function formatTime(value: DateInput): string {
  if (!value) return ''
  return new Date(value).toLocaleTimeString()
}

export function formatMonth(yyyymm: string): string {
  if (yyyymm.length !== 6) return yyyymm
  const year = parseInt(yyyymm.substring(0, 4))
  const month = parseInt(yyyymm.substring(4, 6)) - 1
  return new Date(year, month).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
}
