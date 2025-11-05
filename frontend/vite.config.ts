import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/recipes': 'http://localhost:8000',
      '/extract-recipe': 'http://localhost:8000',
      '/db-health': 'http://localhost:8000'
    }
  },
  build: {
    outDir: 'dist'
  }
})
