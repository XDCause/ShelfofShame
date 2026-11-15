// The order hobbies are listed in, everywhere: starred (favourite) ones first, then the rest, each group A-Z by name.
// Kept apart from index.js so it can be tested without loading every hobby.
const byName = (a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })

export function orderModules(modules, favourites = []) {
  const stars = new Set(favourites ?? [])
  return [...modules].sort((a, b) => (stars.has(b.id) - stars.has(a.id)) || byName(a, b))
}
