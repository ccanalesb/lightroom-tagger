import { create } from 'zustand'
import { io, Socket } from 'socket.io-client'
import { WS_DEFAULT_URL } from '../constants/strings'

interface SocketState {
  socket: Socket | null
  connected: boolean
  
  connect: () => void
  disconnect: () => void
}

const WS_URL = import.meta.env.VITE_WS_URL || WS_DEFAULT_URL

export const useSocketStore = create<SocketState>((set, get) => ({
  socket: null,
  connected: false,
  
  connect: () => {
    const socket = io(WS_URL)
    
    socket.on('connect', () => set({ connected: true }))
    socket.on('disconnect', () => set({ connected: false }))
    
    set({ socket })
  },
  
  disconnect: () => {
    get().socket?.disconnect()
    set({ socket: null, connected: false })
  },
}))