// Copy the drawing canvas's fonts into public/ so the app serves them itself (Excalidraw would
// otherwise fetch them from a CDN, which the content security policy blocks). Run before each
// build (npm run build). All of them, Xiaolai too (12.5 MB, for Chinese text): a browser only
// downloads a font file when text needs it.
import { cpSync, existsSync, readdirSync, rmSync } from 'node:fs'

const from = 'node_modules/@excalidraw/excalidraw/dist/prod/fonts'
const to = 'public/fonts'
if (existsSync(to)) rmSync(to, { recursive: true })
for (const font of readdirSync(from)) {
  cpSync(`${from}/${font}`, `${to}/${font}`, { recursive: true })
}
console.log(`Excalidraw fonts copied to ${to}`)
