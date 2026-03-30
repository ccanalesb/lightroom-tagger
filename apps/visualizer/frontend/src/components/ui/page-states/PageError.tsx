import { MSG_ERROR_PREFIX } from '../../../constants/strings'

export function PageError({ message }: { message: string }) {
  return (
    <div className="text-center py-12">
      <p className="text-red-600">{MSG_ERROR_PREFIX} {message}</p>
    </div>
  )
}
