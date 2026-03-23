import { ReactNode } from 'react'

interface MetadataSectionProps {
  title: string
  children: ReactNode
}

export function MetadataSection({ title, children }: MetadataSectionProps) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        {title}
      </h4>
      <div className="bg-gray-50 rounded-lg p-4">
        {children}
      </div>
    </div>
  )
}
