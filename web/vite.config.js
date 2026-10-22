import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Only used by `npm run dev` (hot-reload development outside Docker):
  // forwards /api calls to the API container's published port, like nginx does in Docker.
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
  // The web code's own tests (run_web_tests.ps1, part of test_all.ps1): src/**/*.test.{js,jsx} in a pretend browser
  // (jsdom). They never reach the API - each test fakes the api.js calls it needs.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
    setupFiles: ['src/tests/setup.js'],          // (what jsdom lacks: matchMedia)
  },
})
