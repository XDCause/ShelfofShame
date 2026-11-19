// "Share my shelf" (ShelfShare.jsx): your board games as ONE web page file to send to someone - by message, email or a
// Drive link. The app itself stays on the home network (no public link, by design): this is a snapshot that opens in
// any browser with no sign-in. The cards are plain HTML (they show even where scripts are blocked, e.g. an email
// preview); a small script inside adds search, "how many players" and "how long" filters and sorting.
// Never in it: what you paid, notes, shops, dates bought - only what the options below turn on.

export const OWNED = ['Owned', 'To sell']                        // still yours (as the Games page counts them)

export function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

const WEIGHTS = [[1.8, 'Light'], [2.6, 'Medium-light'], [3.4, 'Medium'], [4.2, 'Medium-heavy'], [9, 'Heavy']]
export const weightWord = (w) => (w ? WEIGHTS.find(([top]) => Number(w) < top)[1] : null)

export function playersText(g) {
  if (!g.min_players && !g.max_players) return null
  if (!g.max_players || g.max_players === g.min_players) return `${g.min_players ?? g.max_players} player${(g.min_players ?? g.max_players) === 1 ? '' : 's'}`
  return `${g.min_players ?? 1}-${g.max_players} players`
}

// Which games go in: the list ('owned' | 'wanted'), with borrowed games too if asked. Expansions whose base game is
// in the list ride on that game's card (when `expansions`), the rest get cards of their own.
export function pickGames(games, { list = 'owned', borrowed = false, expansions = true } = {}) {
  const statuses = list === 'wanted' ? ['Wanted'] : [...OWNED, ...(borrowed ? ['Borrowed'] : [])]
  const chosen = games.filter((g) => statuses.includes(g.status))
  const ids = new Set(chosen.map((g) => g.game_id))
  const riders = {}
  const cards = []
  for (const g of chosen) {
    if (g.kind === 'expansion' && g.base_game_id && ids.has(g.base_game_id)) {
      if (expansions) (riders[g.base_game_id] ??= []).push(g.name)
    } else cards.push(g)
  }
  cards.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
  return cards.map((g) => ({ ...g, riders: (riders[g.game_id] ?? []).sort((a, b) => a.localeCompare(b)) }))
}

function card(g, o) {
  const meta = [playersText(g), g.play_minutes && `${g.play_minutes} min`, g.min_age && `${g.min_age}+`,
    weightWord(g.weight), g.year].filter(Boolean)
  const extra = [o.plays && g.plays ? `Played ${g.plays} time${g.plays === 1 ? '' : 's'}` : null,
    o.rating && g.rating ? `Rated ${g.rating}/10` : null].filter(Boolean)
  const photo = o.photos?.[g.game_id]
  const cats = (g.categories ?? []).slice(0, 4)
  return `<li class="g" data-name="${esc(g.name.toLowerCase())} ${esc(g.designer?.toLowerCase() ?? '')} ${esc(cats.join(' ').toLowerCase())}"`
    + ` data-min="${g.min_players ?? ''}" data-max="${g.max_players ?? ''}" data-time="${g.play_minutes ?? ''}"`
    + ` data-plays="${g.plays ?? 0}" data-rating="${g.rating ?? 0}">`
    + (photo ? `<img src="${photo}" alt="" loading="lazy">` : `<div class="ph" aria-hidden="true">${esc(g.name.slice(0, 1).toUpperCase())}</div>`)
    + `<div class="b"><h2>${o.links && g.bgg_url ? `<a href="${esc(g.bgg_url)}" target="_blank" rel="noopener noreferrer">${esc(g.name)}</a>` : esc(g.name)}</h2>`
    + (meta.length ? `<p class="m">${meta.map(esc).join(' · ')}</p>` : '')
    + (g.designer ? `<p class="d">${esc(g.designer)}</p>` : '')
    + (cats.length ? `<p class="c">${cats.map((c) => `<span>${esc(c)}</span>`).join('')}</p>` : '')
    + (g.riders.length ? `<p class="x">+ ${esc(g.riders.join(', '))}</p>` : '')
    + (extra.length ? `<p class="e">${extra.map(esc).join(' · ')}</p>` : '')
    + '</div></li>'
}

const STYLE = `
:root{--bg:#f6f4f1;--card:#fff;--ink:#1f1d1b;--soft:#6a645e;--line:#e3ded8;--hue:#a8466f;--chip:#f3e6ec}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--card:#211e1c;--ink:#f1ece6;--soft:#b2aaa1;--line:#3a3532;--hue:#e590b5;--chip:#3a2630}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header,main,footer{max-width:1100px;margin:0 auto;padding:0 16px}header{padding-top:28px}
h1{margin:0;font-size:1.9rem;letter-spacing:-.01em}.sub{margin:.25rem 0 0;color:var(--soft)}.note{margin:.75rem 0 0}
.f{display:flex;flex-wrap:wrap;gap:8px 12px;margin:18px 0 6px;align-items:end}.f label{display:flex;flex-direction:column;font-size:.8rem;color:var(--soft);gap:2px}
.f input,.f select{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-height:44px}
.f input{min-width:min(260px,100%)}#n{color:var(--soft);font-size:.9rem;margin:6px 0 12px}
ul{list-style:none;padding:0;margin:0 0 32px;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.g{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.g img,.ph{width:100%;aspect-ratio:4/3;object-fit:contain;background:var(--chip);display:block}
.ph{display:flex;align-items:center;justify-content:center;font-size:3rem;font-weight:700;color:var(--hue)}
.b{padding:10px 12px 12px}h2{margin:0 0 4px;font-size:1.05rem;line-height:1.25}h2 a{color:inherit}
.b p{margin:3px 0;font-size:.88rem}.m{font-weight:600}.d,.e{color:var(--soft)}.x{color:var(--hue)}
.c{display:flex;flex-wrap:wrap;gap:4px}.c span{background:var(--chip);border-radius:99px;padding:1px 8px;font-size:.75rem}
[hidden]{display:none!important}footer{color:var(--soft);font-size:.8rem;padding-bottom:28px}
@media print{.f,#n{display:none}ul{grid-template-columns:repeat(3,1fr)}.g{break-inside:avoid}}`

// The filters: players (a game fits when min <= n <= max; unknown counts fit), time (up to; unknown fits), sort.
const SCRIPT = `
(function(){var q=document.getElementById('q'),p=document.getElementById('p'),t=document.getElementById('t'),s=document.getElementById('s'),
list=document.getElementById('games'),n=document.getElementById('n'),all=[].slice.call(list.children);
function num(v){return v===''?null:Number(v)}
function run(){var w=q.value.trim().toLowerCase(),pl=Number(p.value),tm=Number(t.value),shown=0;
all.forEach(function(li){var d=li.dataset,mn=num(d.min),mx=num(d.max),ti=num(d.time),ok=(!w||d.name.indexOf(w)>=0)
&&(!pl||((mn===null||mn<=pl)&&(mx===null&&mn===null||(mx===null?mn:mx)>=pl)))&&(!tm||ti===null||ti<=tm);li.hidden=!ok;if(ok)shown++});
var key=s.value,sorted=all.slice().sort(function(a,b){if(key==='time')return (num(a.dataset.time)||1e9)-(num(b.dataset.time)||1e9);
if(key==='plays'||key==='rating')return Number(b.dataset[key])-Number(a.dataset[key]);return 0});
sorted.forEach(function(li){list.appendChild(li)});n.textContent=shown===all.length?all.length+' games':shown+' of '+all.length+' games'}
[q,p,t,s].forEach(function(el){el.addEventListener('input',run)});run()})();`

// The whole file. games: from api.listBoardGames(); o: {list, title, note, made (a date text), photos {game_id: data URL},
// rating, plays, links, borrowed, expansions}.
export function shelfHtml(games, o = {}) {
  const cards = pickGames(games, o)
  const title = (o.title ?? '').trim() || (o.list === 'wanted' ? "Games I'd like" : 'My board games')
  const players = [1, 2, 3, 4, 5, 6, 7, 8].map((k) => `<option value="${k}">${k}${k === 8 ? '+' : ''}</option>`).join('')
  const sorts = [['name', 'Name'], ['time', 'Quickest first'], ...(o.plays ? [['plays', 'Most played']] : []),
    ...(o.rating ? [['rating', 'Highest rated']] : [])].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>${esc(title)}</title><style>${STYLE}</style></head>
<body><header><h1>${esc(title)}</h1><p class="sub">${cards.length} game${cards.length === 1 ? '' : 's'}${o.made ? ` · as of ${esc(o.made)}` : ''}</p>
${o.note?.trim() ? `<p class="note">${esc(o.note.trim())}</p>` : ''}</header>
<main><div class="f">
<label>Search<input id="q" type="search" placeholder="Name, designer, type..."></label>
<label>Players<select id="p"><option value="">Any</option>${players}</select></label>
<label>Time<select id="t"><option value="">Any</option><option value="30">Up to 30 min</option><option value="60">Up to an hour</option><option value="90">Up to 90 min</option><option value="120">Up to 2 hours</option></select></label>
<label>Sort<select id="s">${sorts}</select></label></div>
<p id="n" aria-live="polite">${cards.length} games</p>
<ul id="games">${cards.map((g) => card(g, o)).join('\n')}</ul></main>
<footer>Made with Off the Clock.${o.links ? ' Game links go to BoardGameGeek.' : ''}</footer>
<script>${SCRIPT}</script></body></html>
`
}

// A game's photo as a small JPEG data URL (fits the file: ~15-30 KB each). null when it can't be read.
export async function thumb(url, side = 360) {
  try {
    const res = await fetch(url, { credentials: 'same-origin' })
    if (!res.ok) return null
    const bitmap = await createImageBitmap(await res.blob())
    const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.8)
  } catch {
    return null
  }
}
