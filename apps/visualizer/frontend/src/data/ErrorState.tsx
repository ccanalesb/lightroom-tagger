import { Button } from '../components/ui/Button'

interface Props {
  error: Error
  reset: () => void
  title?: string
}

export function ErrorState({ error, reset, title = 'Something went wrong' }: Props) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center space-y-4">
      <p className="text-text font-medium">{title}</p>
      <p className="text-text-secondary text-sm">{error.message}</p>
      <Button variant="secondary" size="sm" onClick={reset}>
        Retry
      </Button>
    </div>
  )
}
