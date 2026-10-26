import { useState } from 'react'
import { api, imageUrl } from '../api.js'

// The one look-up box for supplies, shared by "Add a supply" and the wishlist's "+ Add" (the wishlist used to
// ask Tamiya only, so what Add a supply found couldn't be found there). Type an item number, a paint code or
// words: the API asks Tamiya, Trumpeter and / or Stedi. Two makers with the number, or words matching several
// Stedi tools = a list to pick from. onFound(result) fills in the form.
export default function ItemLookup({ onFound }) {
  const [code, setCode] = useState('')
  const [choices, setChoices] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  const lookup = async () => {
    if (!code.trim()) return
    setBusy(true)
    setMessage(null)
    try {
      const { found: hits, missed, choices: matches } = await api.lookupItem(code.trim())
      if (matches) {                           // words: Stedi's tools that match - you pick one
        setChoices(matches)
        return
      }
      const unsure = missed.filter((m) => ![404, 409, 422].includes(m.status)).map((m) => `${m.maker}: ${m.message}`)
      if (hits.length > 1) setChoices(hits)
      else await pick(hits[0], hits.length + missed.length > 1, unsure)
    } catch (e) {
      setMessage({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const pick = async (r, say = false, unsure = []) => {
    if (r.sku && !r.product_code) {            // a Stedi search result: look that tool up properly first
      setBusy(true)
      try {
        r = (await api.lookupItem(r.sku)).found[0]
      } catch (e) {
        setMessage({ tone: 'error', text: e.message })
        return
      } finally {
        setBusy(false)
      }
      say = true
    }
    const { maker } = r
    setChoices(null)
    onFound(r)                                 // (a warning on the result is shown by the panel, with the result)
    if (r.warning) setMessage(null)
    else if (maker === 'Trumpeter' && r.is_tool === false) {
      setMessage({ tone: 'low', text: `That's a Trumpeter kit (${r.item_type ?? 'a model'}) - kits usually go in Models.` })
    } else if (unsure.length) setMessage({ tone: 'low', text: `Found at ${maker}. Couldn't check the other site (${unsure.join('; ')}).` })
    else if (r.price_usd != null) setMessage({ tone: 'ok', text: `Found at Stedi: US$${r.price_usd.toFixed(2)} on steditools.com (US dollars - put in your price).` })
    else if (say) setMessage({ tone: 'ok', text: `Found at ${maker}.` })
    else setMessage(null)
  }

  return (
    <>
      <div className="lookup-row">
        <label className="field">
          <span className="field-label">or item number, paint code - or a Stedi tool</span>
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. XF-76, 81776, 08005, MS-106 or nipper"
            autoCapitalize="characters"
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookup() } }} />
        </label>
        <button type="button" className="secondary" onClick={lookup} disabled={busy || !code.trim()}>
          {busy ? 'Looking up...' : 'Look up'}
        </button>
      </div>
      {message && <p className={`alert ${message.tone} small`} role="alert">{message.text}</p>}
      {choices && (
        <section aria-label="Which one">
          <p className="hint">{choices[0]?.sku ? `${choices.length} Stedi tool${choices.length > 1 ? 's' : ''} match. Which is yours?`
            : `Tamiya and Trumpeter both have item ${code.trim()}. Which is yours?`}</p>
          <ul className="list kit-choices">
            {choices.map((c) => (
              <li key={c.sku ?? c.maker}>
                <button type="button" className="row-button" onClick={() => pick(c)}>
                  {c.has_image ? <img className="thumb" src={imageUrl(c)} alt="" loading="lazy" />
                    : c.image ? <img className="thumb" src={c.image} alt="" loading="lazy" referrerPolicy="no-referrer" />
                      : <span className="thumb thumb-empty" aria-hidden="true" />}
                  <span><strong>{c.sku ?? c.maker}</strong> · {c.name ?? c.title}{c.version && <span className="muted"> · {c.version}</span>}
                    {c.price_usd != null && <span className="muted small"> · US${c.price_usd.toFixed(2)}</span>}
                    {c.available === false && <span className="muted small"> · sold out</span>}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
