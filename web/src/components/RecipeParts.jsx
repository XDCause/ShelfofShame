import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import PaintCheck from './PaintCheck.jsx'
import { Swatch } from './supplyExtras.jsx'

// Paint recipes (api/app/recipes.py): a named list of steps, each a paint (yours, or typed) and a note.
//   RecipeCard      one recipe: its steps, "can I paint this now?", copy to a model, edit, delete
//   RecipeEditor    the form (name, where it sits, steps)
//   ModelRecipes    the section on a model's panel (its recipes, reuse a saved one, "can I paint it now?")
//   RecipesPage     every recipe, on its own page

const blankStep = () => ({ label: '', paint_text: '', note: '' })

function useRecipeData() {
  const [supplies, setSupplies] = useState([])
  const [models, setModels] = useState([])
  useEffect(() => {
    api.listSupplies().then((all) => setSupplies(all.filter((s) => s.category === 'Paint'))).catch(() => {})
    api.listModels().then((all) => setModels(all.filter((m) => m.status !== 'Gone'))).catch(() => {})
  }, [])
  return { supplies, models }
}

export function RecipeEditor({ recipe, modelId, supplies, models, pickModel = false, onSaved, onCancel }) {
  const [name, setName] = useState(recipe?.name ?? '')
  const [notes, setNotes] = useState(recipe?.notes ?? '')
  const [unit, setUnit] = useState(recipe?.unit ?? '')
  const [model, setModel] = useState(recipe?.model_id ?? modelId ?? '')
  const [steps, setSteps] = useState(recipe?.steps?.length
    ? recipe.steps.map((s) => ({ label: s.label ?? '', paint_text: s.paint_text, note: s.note ?? '' })) : [blankStep()])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const setStep = (i, patch) => setSteps((all) => all.map((s, k) => (k === i ? { ...s, ...patch } : s)))
  const move = (i, by) => setSteps((all) => {
    const to = i + by
    if (to < 0 || to >= all.length) return all
    const next = [...all]
    ;[next[i], next[to]] = [next[to], next[i]]
    return next
  })

  const save = async () => {
    setBusy(true)
    setError('')
    const body = {
      name, notes: notes || null, unit: unit || null, model_id: model === '' ? null : Number(model),
      steps: steps.filter((s) => s.paint_text.trim()).map((s) => ({
        label: s.label || null, paint_text: s.paint_text, note: s.note || null,
        // a paint you typed exactly as it's named in your supplies is linked to it
        supply_id: supplies.find((x) => x.name.toLowerCase() === s.paint_text.trim().toLowerCase())?.supply_id ?? null,
      })),
    }
    try {
      onSaved(recipe ? await api.updateRecipe(recipe.recipe_id, body) : await api.addRecipe(body))
    } catch (e) { setError(e.message); setBusy(false) }
  }

  return (
    <form className="rcp-form" onSubmit={(e) => { e.preventDefault(); save() }}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <label className="field"><span className="field-label">Recipe name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Blood red armour" required /></label>
      <div className="quick-grid">
        {pickModel && (
          <label className="field"><span className="field-label">On a model (optional)</span>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">Kept on its own</option>
              {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
            </select></label>
        )}
        <label className="field"><span className="field-label">Mini or unit (optional)</span>
          <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Intercessors" /></label>
      </div>
      <ol className="rcp-steps">
        {steps.map((s, i) => (
          <li key={i} className="rcp-step-edit">
            <input value={s.label} onChange={(e) => setStep(i, { label: e.target.value })} placeholder="base, wash..."
              aria-label={`Step ${i + 1} kind`} list="rcp-labels" />
            <input value={s.paint_text} onChange={(e) => setStep(i, { paint_text: e.target.value })} list="rcp-paints"
              placeholder="Paint (yours, or any name)" aria-label={`Step ${i + 1} paint`} />
            <input value={s.note} onChange={(e) => setStep(i, { note: e.target.value })} placeholder="Note"
              aria-label={`Step ${i + 1} note`} />
            <span className="rcp-step-buttons">
              <button type="button" className="icon-btn small" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move step ${i + 1} up`}>↑</button>
              <button type="button" className="icon-btn small" onClick={() => move(i, 1)} disabled={i === steps.length - 1} aria-label={`Move step ${i + 1} down`}>↓</button>
              <button type="button" className="icon-btn small" onClick={() => setSteps((all) => all.filter((_, k) => k !== i))} aria-label={`Remove step ${i + 1}`}>✕</button>
            </span>
          </li>
        ))}
      </ol>
      <datalist id="rcp-labels">{['base', 'layer', 'shade', 'wash', 'highlight', 'drybrush', 'glaze', 'edge', 'varnish'].map((l) => <option key={l} value={l} />)}</datalist>
      <datalist id="rcp-paints">{supplies.map((s) => <option key={s.supply_id} value={s.name} />)}</datalist>
      <button type="button" className="plain" onClick={() => setSteps((all) => [...all, blankStep()])}>+ Add a step</button>
      <label className="field"><span className="field-label">Notes</span>
        <textarea rows="2" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Thin the wash 1:1..." /></label>
      <div className="button-row">
        <button type="submit" className="primary" disabled={busy || !name.trim()}>Save recipe</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

export function RecipeCard({ recipe, supplies, models, onChanged, onOpenSupply, onError }) {
  const [editing, setEditing] = useState(false)
  const [copyTo, setCopyTo] = useState('')
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState('')
  const run = async (fn, msg) => {
    setBusy(true)
    try { await fn(); if (msg) setSaid(msg); onChanged() } catch (e) { onError?.(e.message) } finally { setBusy(false) }
  }
  if (editing) {
    return <RecipeEditor recipe={recipe} supplies={supplies} models={models} pickModel
      onSaved={() => { setEditing(false); onChanged() }} onCancel={() => setEditing(false)} />
  }
  return (
    <article className="rcp-card">
      <h5 className="rcp-title">{recipe.name}
        {(recipe.model_name || recipe.unit) && <span className="muted small"> · {[recipe.model_name, recipe.unit].filter(Boolean).join(' · ')}</span>}</h5>
      {recipe.steps.length > 0 && (
        <ol className="rcp-steps">
          {recipe.steps.map((s) => (
            <li key={s.step_id} className="rcp-step">
              {s.label && <span className="tag">{s.label}</span>}
              <Swatch hex={s.swatch} />
              {s.supply_id
                ? <button type="button" className="link-plain" onClick={() => onOpenSupply?.(s.supply_id)}>{s.paint_text}</button>
                : <span>{s.paint_text}</span>}
              {s.note && <span className="muted small"> - {s.note}</span>}
            </li>
          ))}
        </ol>
      )}
      {recipe.notes && <p className="small muted">{recipe.notes}</p>}
      <PaintCheck check={{ ...recipe.check, items: recipe.steps }} showItems={false} busy={busy}
        onWishlist={() => run(async () => {
          const r = await api.recipeToWishlist(recipe.recipe_id)
          setSaid(r.added.length ? `Added to the wishlist: ${r.added.join(', ')}.` : 'Nothing new to add.')
        })} />
      {said && <p className="save-flash" role="status">{said}</p>}
      <div className="button-row">
        <button type="button" className="secondary" onClick={() => setEditing(true)}>Edit</button>
        <select value={copyTo} onChange={(e) => setCopyTo(e.target.value)} aria-label="Use this recipe on a model">
          <option value="">Use on a model...</option>
          {models.filter((m) => m.model_id !== recipe.model_id).map((m) => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
        </select>
        {copyTo && <button type="button" className="secondary" disabled={busy}
          onClick={() => run(() => api.copyRecipe(recipe.recipe_id, { model_id: Number(copyTo) }), 'Copied to that model ✓').then(() => setCopyTo(''))}>Copy</button>}
        <button type="button" className="plain destructive" disabled={busy}
          onClick={() => window.confirm(`Delete the recipe "${recipe.name}"?`) && run(() => api.deleteRecipe(recipe.recipe_id))}>Delete</button>
      </div>
    </article>
  )
}

// On a model's panel: its recipes, a saved one to reuse, and whether you can paint its whole paint list now.
export function ModelRecipes({ model, onOpenSupply, refreshKey = 0 }) {
  const { supplies, models } = useRecipeData()
  const [recipes, setRecipes] = useState(null)
  const [library, setLibrary] = useState([])
  const [check, setCheck] = useState(null)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const [said, setSaid] = useState('')
  const [version, setVersion] = useState(0)
  const id = model.model_id
  useEffect(() => {
    api.listRecipes(id).then(setRecipes).catch((e) => setError(e.message))
    api.listRecipes().then((all) => setLibrary(all.filter((r) => r.model_id !== id))).catch(() => {})
    if (model.paints_total > 0) api.modelPaintCheck(id).then(setCheck).catch(() => setCheck(null))
  }, [id, model.paints_total, model.paints_have, refreshKey, version])
  const again = useCallback(() => setVersion((v) => v + 1), [])

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Paint recipes{recipes?.length > 0 && ` · ${recipes.length}`}</h4>
        {!adding && <button type="button" className="chip-btn" onClick={() => setAdding(true)}>+ New recipe</button>}
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      {check && check.total > 0 && (
        <details className="rcp-check">
          <summary>Can I paint this now? <strong>{check.ready ? 'Yes ✓' : `Not yet (${check.to_buy} to get)`}</strong></summary>
          <PaintCheck check={check} onOpenSupply={onOpenSupply}
            onWishlist={async () => {
              try {
                const r = await api.modelPaintsToWishlist(id)
                setSaid(r.added.length ? `Added to the wishlist: ${r.added.join(', ')}.` : 'Nothing new to add.')
                again()
              } catch (e) { setError(e.message) }
            }} />
          {said && <p className="save-flash" role="status">{said}</p>}
        </details>
      )}
      {adding && (
        <RecipeEditor modelId={id} supplies={supplies} models={models}
          onSaved={() => { setAdding(false); again() }} onCancel={() => setAdding(false)} />
      )}
      {recipes?.map((r) => (
        <RecipeCard key={r.recipe_id} recipe={r} supplies={supplies} models={models} onOpenSupply={onOpenSupply}
          onChanged={again} onError={setError} />
      ))}
      {recipes?.length === 0 && !adding && <p className="muted small">None yet: write down how you painted it, or reuse one from another model.</p>}
      {library.length > 0 && (
        <label className="field">
          <span className="field-label">Reuse a saved recipe here</span>
          <select value="" onChange={async (e) => {
            if (!e.target.value) return
            try { await api.copyRecipe(Number(e.target.value), { model_id: id }); again() } catch (err) { setError(err.message) }
          }}>
            <option value="">Pick one...</option>
            {library.map((r) => <option key={r.recipe_id} value={r.recipe_id}>{r.name}{r.model_name ? ` (${r.model_name})` : ''}</option>)}
          </select>
        </label>
      )}
    </section>
  )
}

// Every recipe: kept on its own or on a model.
export default function RecipesPage({ onOpenSupply }) {
  const { supplies, models } = useRecipeData()
  const [recipes, setRecipes] = useState(null)
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  useEffect(() => { api.listRecipes().then(setRecipes).catch((e) => setError(e.message)) }, [version])
  const again = () => setVersion((v) => v + 1)
  return (
    <section className="page">
      <div className="toolbar">
        <h2 className="section-title grow">Paint recipes</h2>
        {!adding && <button type="button" className="primary" onClick={() => setAdding(true)}>+ New recipe</button>}
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      {adding && <div className="card"><RecipeEditor supplies={supplies} models={models} pickModel
        onSaved={() => { setAdding(false); again() }} onCancel={() => setAdding(false)} /></div>}
      {!recipes ? <p className="muted loading">Loading...</p> : recipes.length === 0 && !adding
        ? <p className="empty card">No recipes yet. A recipe is the steps you painted something with: base, wash, highlight, each with its paint.</p>
        : recipes.map((r) => (
          <div key={r.recipe_id} className="card">
            <RecipeCard recipe={r} supplies={supplies} models={models} onOpenSupply={onOpenSupply} onChanged={again} onError={setError} />
          </div>
        ))}
    </section>
  )
}
