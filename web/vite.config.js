import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Only used by `npm run dev` (hot-reload development outside Docker):
  // forwards /api calls to the API container's published port, like nginx does in Docker.
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
