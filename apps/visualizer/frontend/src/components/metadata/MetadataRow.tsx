interface MetadataRowProps {
  label: string
  value: string
  monospace?: boolean
}

export function MetadataRow({ label, value, monospace = false }: MetadataRowProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:justify-between sm:gap-4">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-sm text-gray-900 text-right ${monospace ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  )
}
