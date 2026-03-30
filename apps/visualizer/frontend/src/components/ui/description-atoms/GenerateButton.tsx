import {
  DESC_PAGE_GENERATE,
  DESC_PAGE_REGENERATE,
  DESC_PAGE_GENERATING,
} from '../../../constants/strings'

interface GenerateButtonProps {
  hasDescription: boolean
  generating: boolean
  onClick: (e?: React.MouseEvent) => void
}

export function GenerateButton({ hasDescription, generating, onClick }: GenerateButtonProps) {
  const label = generating
    ? DESC_PAGE_GENERATING
    : hasDescription
      ? DESC_PAGE_REGENERATE
      : DESC_PAGE_GENERATE

  const style = hasDescription
    ? 'border border-gray-300 text-gray-600 hover:bg-gray-50'
    : 'bg-indigo-600 text-white hover:bg-indigo-700'

  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick(e) }}
      disabled={generating}
      className={`flex-shrink-0 px-3 py-1 rounded text-xs font-medium transition-colors ${style} disabled:opacity-50`}
    >
      {label}
    </button>
  )
}
