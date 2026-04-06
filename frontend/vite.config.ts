/**
 * LIÇÃO V1: NUNCA remover regras de proxy.
 * Cada rota documentada com comentário.
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  cacheDir: '/tmp/vite-cache-epi',
  server: {
    port: 3000,
    usePolling: true,
    proxy: {
      '/api': { target: 'http://localhost:5001', changeOrigin: true, secure: false },
      '/health': { target: 'http://localhost:5001', changeOrigin: true, secure: false },
      '/socket.io': { target: 'http://localhost:5001', changeOrigin: true, ws: true }
    }
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: { manualChunks: { vendor: ['react', 'react-dom', 'react-router-dom'] } }
    }
  }
})
