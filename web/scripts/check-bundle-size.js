// Fails the build when the app's main download grows past LIMIT_KB (compressed, as the browser gets it).
//
// The main file (dist/assets/index-*.js, the one index.html loads) is what every first visit waits for. Each hobby's
// pages and panels load only when opened (modules/lazy.js), which took it from about 350 KB to about 220 KB
// compressed (health check, 2026-10-21). Something big imported straight into core, Home or a manifest would pull a
// hobby's pages - or a library like Leaflet - back in; this notices. If a real need grows it, raise the limit here,
// on purpose, with a line saying why.
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const LIMIT_KB = 260
const dist = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

const html = readFileSync(join(dist, 'index.html'), 'utf8')
const entry = html.match(/src="\/(assets\/index-[^"]+\.js)"/)?.[1]
if (!entry) {
  console.error('check-bundle-size: no main script in dist/index.html')
  process.exit(1)
}
const kb = (bytes) => Math.round(bytes / 1024)
const main = readFileSync(join(dist, entry))
const size = kb(gzipSync(main).length)
const all = readdirSync(join(dist, 'assets')).filter((f) => f.endsWith('.js')).length
console.log(`check-bundle-size: main ${entry} ${kb(main.length)} KB (${size} KB compressed, limit ${LIMIT_KB} KB); ${all} script files in all`)
if (size > LIMIT_KB) {
  console.error(`check-bundle-size: the main download is ${size} KB compressed - over the ${LIMIT_KB} KB limit. ` +
    'Is a hobby page, a panel or a big library imported straight into core, Home or a manifest? Load it with part() ' +
    '(modules/lazy.js) or a dynamic import().')
  process.exit(1)
}
