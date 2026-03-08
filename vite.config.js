import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/analyze': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/tools': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/debug': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
    port: 5173,
    host: 'localhost',
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
