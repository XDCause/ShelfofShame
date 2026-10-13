import { buildProgress, underwayName } from '../modules/models/steps.jsx'

// How far the build has got: the hobby's steps in order (Gundam: Built, Panel lined, Decals,
// Top coat), ticked up to the last one done. While the kit is In progress, the next step shows
// half-filled as "underway" (Building, Painting...), so a kit you've started but not built yet
// still shows where it's at. Tap a step to say you've done it; tap the last ticked step again to
// untick it. Ticking a step on a kit you haven't started starts it.
// Warhammer boxes also count the minis painted ("3 of 10").
export default function BuildSteps({ model, stages, save }) {
  const { steps, reached, underway } = buildProgress(model, stages)
  const pick = (i) => save({ stage: i === reached ? (steps[i - 1] ?? null) : steps[i] },
    i === reached ? 'Step unticked' : `${steps[i]} ✓`)
  const many = model.hobby === 'Warhammer' && model.figures > 1

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Build steps</h4>
        {underway >= 0 && <span className="pill tint">Now: {underwayName(steps[underway])}</span>}
      </div>
      <ol className="steps" style={{ '--n': steps.length }}>
        {steps.map((s, i) => (
          <li key={s} className={i === underway ? 'underway' : undefined}>
            <button type="button" aria-pressed={i <= reached} onClick={() => pick(i)}
              aria-label={`${s}${i <= reached ? ' (done)' : i === underway ? ' (underway)' : ''}`}
              title={i === underway ? `${underwayName(s)} now. Tap when it's ${s.toLowerCase()}.` : undefined}>
              <span className="step-dot" aria-hidden="true">{i <= reached ? '✓' : i + 1}</span>
              <span className="step-name">{i === underway ? underwayName(s) : s}</span>
            </button>
          </li>
        ))}
      </ol>
      {underway < 0 && reached < 0 && model.status !== 'Finished' && (
        <p className="hint">Not started. Starting the timer or ticking a step moves it to In progress.</p>
      )}
      {many && (
        <div className="minis">
          <span>Minis painted</span>
          <span className="qty">
            <button type="button" aria-label="One fewer painted" disabled={model.figures_done <= 0}
              onClick={() => save({ figures_done: model.figures_done - 1 }, null)}>−</button>
            <span><strong>{model.figures_done}</strong> of {model.figures}</span>
            <button type="button" aria-label="One more painted" disabled={model.figures_done >= model.figures}
              onClick={() => save({ figures_done: model.figures_done + 1 }, null)}>+</button>
          </span>
        </div>
      )}
    </section>
  )
}
