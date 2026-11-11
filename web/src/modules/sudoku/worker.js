// Makes a puzzle away from the page (a Web Worker), so the board never freezes while it searches for a hard one.
//   postMessage({ size, difficulty, technique, seed, budgetMs }) -> { tries } as it goes, then { done: {puzzle, solution, grade} }
import { engineFor, seeded } from './engine.js'

self.onmessage = (e) => {
  const { size = 9, variant = 'classic', difficulty, technique, seed, budgetMs } = e.data
  const rand = seed != null ? seeded(seed) : Math.random
  let last = 0
  const made = engineFor(size, variant).generate(rand, {
    difficulty, technique, budgetMs,
    onTry: (n) => { if (Date.now() - last > 250) { last = Date.now(); self.postMessage({ tries: n }) } },
  })
  self.postMessage({ done: made })
}
