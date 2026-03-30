export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="text-center py-12">
      <p className="text-gray-500">{message}</p>
      {hint && <p className="text-sm text-gray-400 mt-2">{hint}</p>}
    </div>
  )
}
