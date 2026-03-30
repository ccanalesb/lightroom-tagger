import { useEffect } from 'react'
import { useSocketStore } from '../stores/socketStore'
import type { Job } from '../types/job'

interface UseJobSocketOptions {
  onJobCreated?: (job: Job) => void
  onJobUpdated?: (job: Job) => void
}

export function useJobSocket({ onJobCreated, onJobUpdated }: UseJobSocketOptions) {
  const socket = useSocketStore((s) => s.socket)
  const connected = useSocketStore((s) => s.connected)
  const connect = useSocketStore((s) => s.connect)
  const disconnect = useSocketStore((s) => s.disconnect)

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  useEffect(() => {
    if (!socket || !connected) return

    if (onJobCreated) socket.on('job_created', onJobCreated)
    if (onJobUpdated) socket.on('job_updated', onJobUpdated)

    return () => {
      if (onJobCreated) socket.off('job_created', onJobCreated)
      if (onJobUpdated) socket.off('job_updated', onJobUpdated)
    }
  }, [socket, connected, onJobCreated, onJobUpdated])

  return { connected, socket }
}
