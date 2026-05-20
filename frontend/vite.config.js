import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/query': 'http://localhost:8000',
      '/audit': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
