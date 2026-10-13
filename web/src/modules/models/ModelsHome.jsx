import { Link } from 'react-router'
import { api, duration, imageUrl } from '../../api.js'
import { ChevronIcon, PlaneIcon, TimerIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'
import { buildProgress, StepBar } from './steps.jsx'

// Models on Home, in two parts so Home can lay them out:
//   ModelsTiles   unfinished kits (the shelf of shame), time spent building
//   ModelsCards   "Building now": kits in progress, with their build steps
// Both read the same data, fetched once per change.
const load = () => Promise.all([api.listModels(), api.stashSummary()])
  .then(([models, summary]) => ({ models, summary }))

function useShelf() {
  const { refreshKey } = useApp()
  return useShared(`models-home-${refreshKey}`, load)
}

export function ModelsTiles() {
  const { data, error } = useShelf()
  if (error) return <p className="alert error">Models: {error}</p>
  if (!data) return <><StatSkeleton /><StatSkeleton /></>
  return (
    <>
      <Stat to="/models/kits" Icon={PlaneIcon} tone="purple" value={data.summary.shelf_of_shame.kits}
        label="Shelf of shame" sub="kits not finished" />
      <Stat to="/models/kits" Icon={TimerIcon} tone="ok" value={duration(data.summary.total_minutes)}
        label="Time building" sub="all time" />
    </>
  )
}

export function ModelsCards() {
  const { openModel, lookups } = useApp()
  const { data } = useShelf()
  if (!data) return null
  const building = data.models.filter((m) => m.status === 'In progress')

  return (
    <section className="card home-card" aria-labelledby="home-building">
      <h2 id="home-building" className="home-card-title">Building now
        <Link to="/models/kits" className="small">All kits →</Link></h2>
      {building.length === 0 ? <p className="muted small">Nothing on the bench. Start a kit from the stash?</p> : (
        <ul className="list plain-list">
          {building.map((m) => (
            <li key={m.model_id}>
              <button type="button" className="row-button" onClick={() => openModel(m.model_id)}>
                {m.has_image ? <img className="thumb" src={imageUrl(m)} alt="" loading="lazy" />
                  : <span className="thumb thumb-empty" aria-hidden="true" />}
                <span className="grow">
                  <span className="item-title">{m.name}</span>
                  <span className="item-meta">
                    {buildProgress(m, lookups?.stages).text}
                    {m.running_since && <span className="badge out">● Timing</span>}
                  </span>
                  <StepBar model={m} stages={lookups?.stages} />
                </span>
                <ChevronIcon size={16} className="chevron" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
