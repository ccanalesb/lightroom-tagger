const IMAGE_TYPE_CLASSES = {
  catalog: 'bg-blue-100 text-blue-700',
  instagram: 'bg-pink-100 text-pink-700',
} as const

const IMAGE_TYPE_LABELS = {
  catalog: 'CAT',
  instagram: 'IG',
} as const

export function ImageTypeBadge({ type }: { type: 'catalog' | 'instagram' }) {
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${IMAGE_TYPE_CLASSES[type]}`}>
      {IMAGE_TYPE_LABELS[type]}
    </span>
  )
}
