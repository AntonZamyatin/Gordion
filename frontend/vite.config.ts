import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // deck.gl is intentionally isolated in its own chunk (~600 KB / 180 KB gzip).
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          // deck.gl is large; keep it in its own chunk.
          deckgl: ['@deck.gl/core', '@deck.gl/layers', '@deck.gl/react'],
        },
      },
    },
  },
})
