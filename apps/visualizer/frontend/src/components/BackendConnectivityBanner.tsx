import { useEffect, useState } from 'react'
import {
  BACKEND_BUSY_BANNER_BODY,
  BACKEND_BUSY_BANNER_TITLE,
  BACKEND_DISCONNECTED_BANNER_BODY,
  BACKEND_DISCONNECTED_BANNER_TITLE,
} from '../constants/strings'
import { useBackendHealthStore } from '../stores/backendHealthStore'
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
  const httpBusy = useBackendHealthStore((s) => s.httpBusy)
  const [showDisconnectBanner, setShowDisconnectBanner] = useState(false)

  useEffect(() => {
    if (!socket || connected) {
      setShowDisconnectBanner(false)
      return
    }

    const timer = window.setTimeout(() => setShowDisconnectBanner(true), DISCONNECT_GRACE_MS)
    return () => window.clearTimeout(timer)
  }, [socket, connected])

  if (httpBusy) {
    return (
      <div
        className="border-b border-warning bg-warning/10 px-4 py-3 sm:px-6 lg:px-8"
        role="status"
        data-testid="backend-busy-banner"
      >
        <p className="mx-auto max-w-7xl text-sm font-semibold text-text">
          {BACKEND_BUSY_BANNER_TITLE}
        </p>
        <p className="mx-auto mt-1 max-w-7xl text-sm text-text-secondary">
          {BACKEND_BUSY_BANNER_BODY}
        </p>
      </div>
    )
  }

  if (!showDisconnectBanner) {
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
