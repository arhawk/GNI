import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiTarget = process.env.GNI_API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
    },
  },
})
