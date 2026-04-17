import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || '5001'
  const backendUrl = `http://localhost:${backendPort}`
  const allowedHostsRaw = env.DEV_SERVER_ALLOWED_HOSTS?.trim()
  const allowedHosts = allowedHostsRaw
    ? allowedHostsRaw
        .split(',')
        .map((h) => h.trim())
        .filter(Boolean)
    : undefined

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      ...(allowedHosts ? { allowedHosts } : {}),
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        '/socket.io': {
          target: backendUrl,
          ws: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.ts',
    },
  }
})