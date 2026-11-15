// Small pure helpers for the opening trainer (OpeningExplorer.jsx, OpeningTrainer.jsx): tested in tests/openingHelpers.test.js.

// ['e4', 'e5', 'Nf3'] -> "1.e4 e5 2.Nf3" (a line always starts from the first move, so White moves on odd plies).
export function formatLine(sans, from = 0) {
  return sans.map((san, i) => {
    const ply = from + i
    if (ply % 2 === 0) return `${ply / 2 + 1}.${san}`
    return i === 0 ? `${(ply + 1) / 2}...${san}` : san
  }).join(' ')
}

// A position without its move counters, the way the API keys them (python-chess's EPD): the first four FEN fields.
export const epdOf = (fen) => fen.split(' ').slice(0, 4).join(' ')

// The opponent's reply in a drill: one of the options, picked by how often it's played. roll is 0 <= x < 1 (Math.random()).
export function pickReply(options, roll = Math.random()) {
  if (!options?.length) return null
  const total = options.reduce((sum, o) => sum + (o.share || 0), 0)
  if (!total) return options[0]
  let at = roll * total
  for (const o of options) {
    at -= o.share || 0
    if (at < 0) return o
  }
  return options[options.length - 1]
}

// 'e2e4' / 'e7e8q' -> { from: 'e2', to: 'e4' }
export const uciSquares = (uci) => ({ from: uci.slice(0, 2), to: uci.slice(2, 4) })

// Many games as "1.2M", "34k" or "812".
export function gamesText(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e4) return `${Math.round(n / 1e3)}k`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(n)
}

// "You've reached this position 7 times: +3 =1 -3" from the API's `mine`, or null if never.
export function mineText(mine) {
  if (!mine?.games) return null
  return `You've reached this position ${mine.games} time${mine.games === 1 ? '' : 's'}: +${mine.wins} =${mine.draws} -${mine.losses}`
}

// A repertoire's progress as words: "12 learned, 3 due, 5 new of 20".
export function progressText(p) {
  if (!p || !p.total) return 'No cards yet'
  const parts = [`${p.learned} learned`]
  if (p.due) parts.push(`${p.due} due`)
  if (p.new) parts.push(`${p.new} new`)
  return `${parts.join(', ')} of ${p.total}`
}

// Who plays the opening: names that end in "Defense" / "Defence" (and the like) are Black's.
export const suggestColour = (name) => (/defen[cs]e|indian|gambit accepted|pirc|modern|benoni|scandinavian|alekhine/i.test(name) ? 'black' : 'white')
