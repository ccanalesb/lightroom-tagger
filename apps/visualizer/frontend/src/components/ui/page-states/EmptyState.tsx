export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="text-center py-12">
      <p className="text-text-secondary">{message}</p>
      {hint && <p className="text-sm text-text-tertiary mt-2">{hint}</p>}
    </div>
  )
}
