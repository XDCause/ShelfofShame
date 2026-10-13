// How a day felt: the five moods (best first; ids must match MOODS in api/app/db.py), their
// faces and colours, and words to pick from (you can type your own too).
export const MOODS = [
  { id: 'great', face: '😄', label: 'Great', tone: 'ok' },
  { id: 'good', face: '🙂', label: 'Good', tone: 'teal' },
  { id: 'okay', face: '😐', label: 'Okay', tone: 'tint' },
  { id: 'meh', face: '😕', label: 'Meh', tone: 'low' },
  { id: 'rough', face: '😢', label: 'Rough', tone: 'out' },
]
export const moodOf = (id) => MOODS.find((m) => m.id === id) ?? null

export const MOOD_WORDS = [
  'proud', 'relaxed', 'happy', 'grateful', 'creative', 'focused', 'social', 'energised',
  'tired', 'stressed', 'anxious', 'frustrated', 'bored', 'busy', 'sore', 'sick',
]

// A page's face in lists: its mood, else a pen (whiteboard) or a page.
export const pageFace = (p) => moodOf(p.mood)?.face ?? (p.kind === 'whiteboard' ? '🖊️' : '📝')
