import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies the local Python API; `npm run build` emits dist/ served by it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8600' } },
  build: { outDir: 'dist', chunkSizeWarningLimit: 2000 },
})
