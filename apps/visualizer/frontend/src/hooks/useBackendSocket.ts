import { useEffect } from 'react'
import { useSocketStore } from '../stores/socketStore'

/** Ensure the shared Socket.IO client is connected for the lifetime of the shell. */
export function useBackendSocket() {
  const connect = useSocketStore((s) => s.connect)

  useEffect(() => {
    connect()
  }, [connect])
}
