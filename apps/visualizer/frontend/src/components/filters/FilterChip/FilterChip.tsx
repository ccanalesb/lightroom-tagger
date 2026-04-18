import { Badge } from '../../ui/Badge/Badge'
import { Button } from '../../ui/Button/Button'

export type FilterChipProps = {
  text: string
  removeAriaLabel: string
  onRemove: () => void
  disabled?: boolean
}

export function FilterChip({ text, removeAriaLabel, onRemove, disabled }: FilterChipProps) {
  return (
    <Badge variant="default" className="inline-flex items-center gap-1 pr-1">
      <span className="max-w-[14rem] truncate">{text}</span>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="!px-1 !py-0 min-w-0 h-6 text-text-secondary hover:text-text"
        aria-label={removeAriaLabel}
        disabled={disabled}
        onClick={onRemove}
      >
        ×
      </Button>
    </Badge>
  )
}
