import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The offline copy's service worker (src/offline/sw.js) becomes dist/sw.js once everything is built, with BUILD filled
// in: every file the app is made of (what it saves when Settings > Offline copy is turned on) and a version made from
// their contents. A new build = a new version: the phone fetches the new files and drops the old ones.
function offlineWorker() {
  let outDir
  return {
    name: 'offline-worker',
    apply: 'build',
    configResolved(config) { outDir = resolve(config.root, config.build.outDir) },
    closeBundle() {
      const found = []
      const walk = (dir) => {
        for (const e of readdirSync(dir, { withFileTypes: true })) (e.isDirectory() ? walk : (f) => found.push(f))(join(dir, e.name))
      }
      walk(outDir)
      const hash = createHash('sha256')
      const files = []
      for (const path of found.sort()) {
        const url = `/${relative(outDir, path).split('\\').join('/')}`
        if (url === '/sw.js' || url.endsWith('.map')) continue
        hash.update(url).update(readFileSync(path))
        files.push(url)
      }
      const source = readFileSync(resolve(import.meta.dirname, 'src/offline/sw.js'), 'utf8')
      const line = "const BUILD = { version: 'dev', files: [] }"
      if (!source.includes(line)) throw new Error(`offline-worker: src/offline/sw.js no longer has the line ${line}`)
      const version = hash.digest('hex').slice(0, 12)
      writeFileSync(join(outDir, 'sw.js'), source.replace(line, `const BUILD = ${JSON.stringify({ version, files })}`))
      console.log(`offline-worker: dist/sw.js, version ${version}, ${files.length} files to keep offline`)
    },
  }
}

export default defineConfig({
  plugins: [react(), offlineWorker()],
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
