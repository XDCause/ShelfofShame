// Fails the build when two parts of the app style the same class name - the mistake that has quietly
// broken layouts before (.tick, .change, .goal-card, .goal-head were each defined twice for different
// things, and the later one won).
//
// The styles are one long sheet in sections (styles.css lists its files in order; a comment at the start of a line opens a section). A class's "own"
// rule is one whose selector is just that class, maybe with a state or pseudo-element (`.goal-card`,
// `.goal-card:hover`, `.goal-card::after`), written for that class alone. Defining a class's own rule
// in two sections is a clash: two parts of the app picked the same name (or one rule was split up).
// Not counted: rules inside @media (they adjust a class for a screen size), variants (`.goal-card.done`,
// which is how a later part adds to a shared class), longer selectors (`.home .goal-card`), rules
// shared by several classes (`.primary, .secondary { ... }`), and the names in ALLOWED.
//
//   node scripts/check-css-clashes.js            (run by `npm run build`)
import { readFileSync } from 'node:fs'

const CSS = new URL('../src/styles.css', import.meta.url)

// Deliberately styled in more than one section (a base look, then a part of the app adding to it).
const ALLOWED = new Set([
  // the tone system: these share one rule that gives every tone its colours ("Coloured pills, icon
  // squares and tiles share one set of tone colours"), on top of their own shape
  'pill', 'stat-icon', 'thumb-icon',
])

// styles.css lists the files in web/src/styles in order (@import, 2026-10-21): read them as the one long file they
// make up, remembering where each line came from (for the messages).
const lines = []
const origin = []
for (const line of readFileSync(CSS, 'utf8').split('\n')) {
  const part = line.match(/^@import '\.\/(styles\/[^']+\.css)';/)
  if (!part) { lines.push(line); origin.push(`styles.css:${lines.length}`); continue }
  readFileSync(new URL(`../src/${part[1]}`, import.meta.url), 'utf8').split('\n').forEach((l, n) => {
    lines.push(l)
    origin.push(`${part[1]}:${n + 1}`)
  })
}
const owners = new Map()   // class (+ state) -> Map(section -> first line)
let section = '(top of the file)'
let depth = 0              // { } nesting
let mediaDepth = null      // depth at which the current @media / @supports block opened
let selector = ''
let selectorLine = 0

for (let i = 0; i < lines.length; i += 1) {
  const line = lines[i]
  if (depth === 0 && /^\/\*/.test(line)) section = `${line.replace(/^\/\*\s*|\s*\*\/.*$/g, '').slice(0, 60)} (${origin[i]})`
  const code = line.replace(/\/\*.*?\*\//g, '')
  for (const ch of code) {
    if (ch === '{') {
      const sel = selector.trim()
      if (/^@(media|supports|container)/.test(sel)) mediaDepth = mediaDepth ?? depth
      else if (mediaDepth === null && !sel.startsWith('@')) {
        const parts = sel.split(',')
        for (const part of parts.length === 1 ? parts : []) {     // a rule for several classes isn't one's own
          const m = part.trim().match(/^\.([\w-]+)((?:::?[\w-]+(?:\([^)]*\))?)*)$/)    // just the class (+ states)
          if (!m) continue
          const own = m[1]
          if (ALLOWED.has(own)) continue
          const key = `${own}${m[2]}`                                   // .x and .x:hover are different rules
          if (!owners.has(key)) owners.set(key, new Map())
          if (!owners.get(key).has(section)) owners.get(key).set(section, selectorLine || i + 1)
        }
      }
      depth += 1
      selector = ''
    } else if (ch === '}') {
      depth -= 1
      if (mediaDepth !== null && depth === mediaDepth) mediaDepth = null
      selector = ''
    } else if (ch === ';' && depth === 0) {
      selector = ''
    } else {
      if (!selector.trim()) selectorLine = i + 1
      selector += ch
    }
  }
  selector += '\n'
}

const clashes = [...owners].filter(([, where]) => where.size > 1)
if (clashes.length) {
  console.error(`CSS clash: ${clashes.length} class name(s) are styled in more than one part of the styles (web/src/styles).`)
  console.error('Rename one of them (give it the part of the app as a prefix), or add it to ALLOWED in')
  console.error('web/scripts/check-css-clashes.js if it really is shared on purpose.\n')
  for (const [name, where] of clashes) {
    console.error(`  .${name}`)
    for (const [sec, line] of where) console.error(`      ${origin[line - 1]}: in "${sec}"`)
  }
  process.exit(1)
}
console.log(`CSS: no clashes (${owners.size} class names checked).`)
