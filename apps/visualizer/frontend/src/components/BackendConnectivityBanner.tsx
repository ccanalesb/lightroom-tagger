import { useEffect, useState } from 'react'
import {
  BACKEND_DISCONNECTED_BANNER_BODY,
  BACKEND_DISCONNECTED_BANNER_TITLE,
} from '../constants/strings'
import { useSocketStore } from '../stores/socketStore'

const DISCONNECT_GRACE_MS = 2_000

/**
 * Global alert when the backend WebSocket is unreachable. Complements per-page
 * HTTP error boundaries — a blocked event loop may keep sockets alive briefly,
 * but a crash or restart surfaces here quickly.
 */
export function BackendConnectivityBanner() {
  const connected = useSocketStore((s) => s.connected)
  const socket = useSocketStore((s) => s.socket)
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    if (!socket || connected) {
      setShowBanner(false)
      return
    }

    const timer = window.setTimeout(() => setShowBanner(true), DISCONNECT_GRACE_MS)
    return () => window.clearTimeout(timer)
  }, [socket, connected])

  if (!showBanner) {
    return null
  }

  return (
    <div
      className="border-b border-error bg-error/10 px-4 py-3 sm:px-6 lg:px-8"
      role="alert"
      data-testid="backend-connectivity-banner"
    >
      <p className="mx-auto max-w-7xl text-sm font-semibold text-text">
        {BACKEND_DISCONNECTED_BANNER_TITLE}
      </p>
      <p className="mx-auto mt-1 max-w-7xl text-sm text-text-secondary">
        {BACKEND_DISCONNECTED_BANNER_BODY}
      </p>
    </div>
  )
}
