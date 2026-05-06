import { MSG_LOADING } from '../../../constants/strings'

export function PageLoading({ message = MSG_LOADING }: { message?: string }) {
  return (
    <div className="text-center py-12">
      <p className="text-text-secondary">{message}</p>
    </div>
  )
}
