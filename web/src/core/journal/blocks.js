// Building journal pages in code: BlockNote's blocks (the editor's own format), the built-in templates, the prompts,
// and the pages made from what you did (Write about today, a weekly review).

let next = 0
const id = () => `otc-${Date.now().toString(36)}-${(next += 1)}`
const inline = (parts) => (Array.isArray(parts) ? parts : [parts]).filter((p) => p !== '').map((p) => (typeof p === 'string' ? { type: 'text', text: p, styles: {} } : p))
const block = (type, parts = [], props = {}) => ({ id: id(), type, props, content: inline(parts), children: [] })

export const heading = (text, level = 2) => block('heading', text, { level })
export const para = (parts = []) => block('paragraph', parts)
export const bullet = (parts) => block('bulletListItem', parts)
export const check = (text) => block('checkListItem', text, { checked: false })
export const quote = (text) => block('quote', text)
// An @mention of something in the app (journal_text.py KINDS): it links the page to it.
export const mention = (kind, ref, label) => ({ type: 'mention', props: { kind, ref: String(ref), label } })

// What a feed item (activity.py) can be @mentioned as; the rest are written as plain words.
const MENTION_KIND = { model: 'model', game: 'game', videogame: 'videogame', chess: 'chess', book: 'book', trip: 'trip', supply: 'supply', gear: 'gear' }
export const didLine = (d) => {
  const kind = MENTION_KIND[d.kind]
  const name = kind ? [mention(kind, d.ref, d.title)] : [d.title]
  return bullet([`${d.verb} `, ...name, ...(d.detail ? [` · ${d.detail}`] : [])])
}

// The templates that come with the app. Each makes {title, content, tags} for a new page.
export const BUILT_IN = [
  {
    key: 'daily', name: 'Daily reflection', hint: 'Wins, what was hard, tomorrow',
    make: () => ({ title: '', content: [heading('Today'), para(), heading('What went well'), bullet(''), heading('What was hard'), bullet(''),
      heading('Tomorrow I will'), check('')] }),
  },
  {
    key: 'build', name: 'Build log', hint: 'A session at the bench',
    make: () => ({ title: 'Build log', tags: ['build'], content: [heading('Working on'), para(), heading('What I did'), bullet(''),
      heading('Paints and supplies'), bullet(''), heading('Next time'), check(''), heading('Photos'), para()] }),
  },
  {
    key: 'debrief', name: 'Session debrief', hint: 'After a game, a match or the range',
    make: () => ({ title: 'Debrief', tags: ['debrief'], content: [heading('What happened'), para(), heading('Went well'), bullet(''),
      heading('To work on'), bullet(''), heading('One thing to try next time'), para()] }),
  },
  {
    key: 'trip', name: 'Trip day', hint: 'Where you went, the highlight',
    make: () => ({ title: 'Trip day', tags: ['travel'], content: [heading('Where we went'), para(), heading('Highlight'), para(),
      heading('Food'), bullet(''), heading('Tomorrow'), para()] }),
  },
]

// Prompts for an empty page - one a day (the same all day), or shuffle for another.
export const PROMPTS = [
  'What made you smile today?', 'What did you make progress on?', 'What are you looking forward to this week?',
  'What did you learn today, however small?', 'Who made your day better, and how?', 'What would make tomorrow great?',
  'What drained your energy today?', 'What are you grateful for right now?', 'What hobby moment are you proud of lately?',
  'What did you try for the first time?', 'What would you tell yourself a year ago?', 'What are you putting off, and why?',
  'Describe a moment today you want to remember.', 'What went better than you expected?', 'What do you want more of this month?',
  'What was hard today, and how did you handle it?', 'Which goal feels closest? What is the next step?', 'What did you notice outside today?',
  'What is something you could let go of?', 'If today had a title, what would it be?', 'What skill are you building, and how is it going?',
  'What was the best part of your weekend?', 'What surprised you this week?', 'What does a perfect day off look like?',
]
export const promptFor = (day, shift = 0) => {
  const n = [...day].reduce((a, c) => a + c.charCodeAt(0), 0)
  return PROMPTS[(n + shift) % PROMPTS.length]
}

// A page about what you did today (or any day), from the activity feed.
export function todayPage(did) {
  return [heading('What I did'), ...did.map(didLine), heading('How it went'), para()]
}

const MOOD_WORD = { great: 'Great', good: 'Good', okay: 'Okay', meh: 'Meh', rough: 'Rough' }

// A weekly (or monthly) review: the moods, what you did by hobby, goals, then room for your thoughts.
export function reviewPage(r, dayLabel) {
  const content = []
  if (r.moods.length) {
    content.push(heading('How it felt'), ...r.moods.map((m) => bullet(`${dayLabel(m.day)}: ${MOOD_WORD[m.mood]}${m.mood_words.length ? ` (${m.mood_words.join(', ')})` : ''}`)))
  }
  if (r.hobbies.length) {
    content.push(heading('What I did'))
    for (const h of r.hobbies) {
      content.push(heading(`${h.hobby} · ${h.count}`, 3), ...h.items.map(didLine))
    }
  }
  if (r.goals.length) content.push(heading('Goals'), ...r.goals.map(didLine))
  content.push(heading('Best moment'), para(), heading('What I learned'), para(), heading('Next week I want to'), check(''))
  return content
}
