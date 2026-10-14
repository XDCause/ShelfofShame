// How far a build has got, shared by the kit panel, the kit cards and Home.
// A kit's `stage` is the last step DONE. While the kit is In progress, the step after it is
// "underway": the piece is being made but that step isn't finished (e.g. still Building, not yet
// Built). That step shows half-filled, so every kit on the bench shows where it's at.
// Every build ends at Complete; steps passed over on the way (a snap-fit kit with no detailing)
// are in model.skipped_steps and show as skipped, not done.

// What you're doing while a step is underway ("Built" -> "Building").
const UNDERWAY = {
  Built: 'Building', Primed: 'Priming', Painted: 'Painting', Decals: 'Doing decals', Weathered: 'Weathering',
  Based: 'Basing', 'Panel lined': 'Panel lining', 'Top coat': 'Top coating', Complete: 'Finishing off',
}
export const underwayName = (step) => UNDERWAY[step] ?? step

export function buildProgress(model, stages) {
  const steps = stages?.[model.hobby] ?? []
  const reached = steps.indexOf(model.stage) // -1 = nothing done yet
  const skipped = new Set(model.skipped_steps ?? [])
  const underway = model.status === 'In progress' && reached < steps.length - 1 ? reached + 1 : -1
  const skips = skipped.size ? ` (${skipped.size} skipped)` : ''
  let text = ''
  if (underway >= 0) text = `${underwayName(steps[underway])} · step ${underway + 1} of ${steps.length}`
  else if (reached === steps.length - 1 && steps.length) text = `Complete${skips}`
  else if (reached >= 0) text = `${model.stage}, step ${reached + 1} of ${steps.length}`
  return { steps, reached, underway, skipped, text }
}

// A row of segments: done ones filled, the underway one striped.
export function StepBar({ model, stages }) {
  const { steps, reached, underway, skipped } = buildProgress(model, stages)
  if (!steps.length) return null
  return (
    <span className="step-bar" aria-hidden="true">
      {steps.map((s, i) => <span key={s} className={skipped.has(s) ? 'skip' : i <= reached ? 'on' : i === underway ? 'now' : ''} />)}
    </span>
  )
}
