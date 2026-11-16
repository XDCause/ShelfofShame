// Colour marks on the board, for chains and "this or that" thinking. Kept as one flat object in the game's saved state
// (state.c): "12" = cell 12 is coloured; "12:7" = the 7 noted in cell 12 is coloured. Colours are 1-4.
export const COLOURS = [1, 2, 3, 4]
export const COLOUR_NAMES = { 1: 'teal', 2: 'amber', 3: 'green', 4: 'purple' }

export const cellKey = (i) => String(i)
export const noteKey = (i, d) => `${i}:${d}`

// Put a colour on (or take it off if it's already that colour): returns a new object.
export function toggleMark(marks, key, colour) {
  const next = { ...marks }
  if (next[key] === colour) delete next[key]
  else next[key] = colour
  return next
}

// A cell's colour, and a note's colour (0 = none).
export const cellColour = (marks, i) => marks[cellKey(i)] ?? 0
export const noteColour = (marks, i, d) => marks[noteKey(i, d)] ?? 0

// A cell's marks go when a digit is placed in it (its notes are gone, so their colours are too).
export function dropNoteMarks(marks, i) {
  const out = {}
  for (const [k, v] of Object.entries(marks)) if (!k.startsWith(`${i}:`)) out[k] = v
  return out
}
