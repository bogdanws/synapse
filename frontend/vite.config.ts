import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In docker-compose (dev), set API_PROXY_TARGET=http://backend:8000 so the Vite dev server can reach the backend container by its service name.
// For local dev outside docker, this defaults to http://localhost:8000.
const backendTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': backendTarget,
      '/ws': { target: backendTarget, ws: true },
      '/health': backendTarget,
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      reporter: ['text', 'html'],
    },
  },
})
