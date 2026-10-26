import { useState } from 'react'
import { api, imageUrl, today } from '../api.js'
import Drawer from './Drawer.jsx'
import ScanButton from './ScanButton.jsx'
import { Field } from './SupplyFields.jsx'

const FIELDS = ['name', 'hobby', 'brand_id', 'product_code', 'scale', 'grade', 'faction', 'figures', 'status',
  'scalemates_url', 'price_paid', 'purchase_date', 'purchased_from', 'started_on', 'finished_on']
// Only some fields mean anything for each hobby; the others are sent empty.
const ONLY_FOR = { grade: 'Gundam', faction: 'Warhammer', figures: 'Warhammer' }
const NEW_BRAND = 'new:' // brand_id value for a brand you haven't used yet, e.g. "new:Bandai"

// Whose kits each hobby can look up, and what to type for each.
const MAKERS = { 'Scale model': ['Tamiya', 'Hasegawa', 'Trumpeter'], Gundam: ['Bandai'], Warhammer: ['Games Workshop'] }
const LOOKUP_HELP = {
  Tamiya: { label: 'Kit number', example: 'e.g. 32595' },
  Hasegawa: { label: 'Series code or item number from the box', example: 'e.g. JT86 or 09086' },
  Trumpeter: { label: 'Item number from the box', example: 'e.g. 00968' },
  Bandai: { label: 'Code from the box, its barcode, or the name', example: 'e.g. G5057403 or rx-78-2 revive' },
  'Games Workshop': { label: 'Kit name, Games Workshop code or box barcode', example: 'e.g. combat patrol adeptus mechanicus or 59-05' },
}

// Hints that change with the hobby.
const EXAMPLES = {
  'Scale model': { name: 'e.g. M4A3E8 Sherman', code: 'e.g. T32595', scale: 'e.g. 1/48' },
  Warhammer: { name: 'e.g. Intercessors', code: 'e.g. 48-75', scale: 'e.g. 28mm' },
  Gundam: { name: 'e.g. RX-78-2 Gundam (Revive)', code: 'e.g. G5057403', scale: 'e.g. 1/144' },
}

const toForm = (m) => Object.fromEntries(FIELDS.map((f) => [f, m[f] == null ? '' : String(m[f])]))
const toBody = (f, editing) => {
  const body = Object.fromEntries(FIELDS
    .filter((k) => editing || !['started_on', 'finished_on'].includes(k))
    .map((k) => {
      const v = f[k].trim()
      if (v === '' || (ONLY_FOR[k] && ONLY_FOR[k] !== f.hobby)) return [k, k === 'figures' ? 1 : null]
      return [k, ['brand_id', 'figures'].includes(k) && !v.startsWith(NEW_BRAND) ? Number(v) : v]
    }))
  if (String(body.brand_id ?? '').startsWith(NEW_BRAND)) {
    body.brand_name = body.brand_id.slice(NEW_BRAND.length)  // the API adds it to your brands
    body.brand_id = null
  }
  return body
}

// Adding a model (look the kit up by its number first, optionally) or editing its details.
// wanted: a new kit for the wishlist (opened from the wishlist's + Add): it starts as Wanted.
export default function ModelForm({ model, wanted: forWishlist = false, lookups, settings, onClose, onCancel, onSaved }) {
  const [form, setForm] = useState(() => (model ? toForm(model) : {
    ...toForm({}), hobby: 'Scale model', status: forWishlist ? 'Wanted' : 'In stash', figures: '1', purchase_date: today(),
    purchased_from: settings.default_shop ?? '',
  }))
  const [kitCode, setKitCode] = useState('')
  const [makerPick, setMaker] = useState('Tamiya') // whose kit number it is
  const [found, setFound] = useState(null)
  const [choices, setChoices] = useState(null) // several Bandai / Warhammer kits matched a name: pick one
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (f) => (e) => setForm((x) => ({ ...x, [f]: e.target.value }))
  const wanted = form.status === 'Wanted'
  const example = EXAMPLES[form.hobby]

  // A brand's id for the Brand list, or "new:<name>" while it isn't one of your brands yet.
  const brandValue = (name) => {
    const known = lookups.brands.find((b) => b.name === name)
    return known ? String(known.id) : NEW_BRAND + name
  }
  // A new Warhammer / Gundam kit starts with that hobby's usual maker (added to your brands on
  // saving if you haven't used it yet).
  const pickHobby = (hobby) => setForm((f) => {
    const maker = lookups.hobby_brands[hobby]
    if (model) return { ...f, hobby }
    if (!maker) return { ...f, hobby, brand_id: f.brand_id.startsWith(NEW_BRAND) ? '' : f.brand_id }
    return { ...f, hobby, brand_id: brandValue(maker) }
  })
  const makers = MAKERS[form.hobby] ?? []
  const maker = makers.includes(makerPick) ? makerPick : makers[0]
  // Picking a grade fills in its usual scale (HG = 1/144, MG = 1/100...) if there isn't one yet.
  const setGrade = (e) => {
    const grade = e.target.value
    const scale = lookups.gundam_grades[grade.trim().toUpperCase()]
    setForm((f) => ({ ...f, grade, scale: f.scale || scale || '' }))
  }

  // Kit number -> name, scale and box photo from the maker's website (Bandai: from hlj.com).
  const lookup = async (code = kitCode) => {
    setBusy(true)
    setError('')
    setChoices(null)
    try {
      let r, name, scale, grade, faction, figures
      if (maker === 'Games Workshop') {
        r = await api.lookupWarhammer(code.trim())
        if (r.choices) {
          setChoices(r.choices.map((c) => ({ key: c.id, code: `id:${c.id}`, title: c.title, thumb_url: c.image && `${c.image}&width=120`,
            note: [c.price != null && `$${c.price.toFixed(2)}`, c.available ? 'in stock' : 'sold out', c.my_model && 'yours'].filter(Boolean).join(' · ') })))
          setFound(null)
          return
        }
        name = r.name
        faction = r.faction
        figures = r.figures
      } else if (maker === 'Bandai') {
        r = await api.lookupBandai(code.trim())
        if (r.choices) {
          setChoices(r.choices.map((c) => ({ key: c.hlj_code, code: c.hlj_code, title: c.title, thumb_url: c.thumb_url })))
          setFound(null)
          return
        }
        name = r.name
        scale = r.scale
        grade = r.grade
      } else if (maker === 'Trumpeter') {
        r = await api.lookupTrumpeter(code.trim()) // the 5-digit item number (00968)
        name = r.name
        scale = r.scale ?? ''
      } else if (maker === 'Hasegawa') {
        r = await api.lookupHasegawa(code.trim()) // series code (JT86) or item number (09086)
        name = r.name
        scale = r.scale ?? ''
      } else {
        r = await api.lookupTamiya(code.trim())
        // Tamiya kit titles look like "1/48 SCALE MITSUBISHI A6M3/3A ZERO (ZEKE)": split off the scale.
        scale = r.title?.match(/^\s*(1\/\d+)/)?.[1] ?? ''
        name = (r.suggested?.name ?? r.title ?? '').replace(/^\s*1\/\d+\s*(scale\s+)?/i, '')
      }
      setFound(r)
      setForm((f) => ({ ...f, name: name || f.name, scale: scale || f.scale, grade: grade || f.grade,
        faction: faction || f.faction, figures: figures ? String(figures) : f.figures,
        brand_id: brandValue(maker), product_code: r.product_code }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = toBody(form, !!model)
      if (body.status === 'Wanted') Object.assign(body, { price_paid: null, purchase_date: null, purchased_from: null })
      onSaved(model ? await api.updateModel(model.model_id, body) : await api.addModel(body))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  // Keys: see ItemPanel - stops a button turning into the submit button mid-click.
  const footer = (
    <>
      <button key="save" type="submit" form="model-form" className="primary" disabled={busy || !form.name.trim()}>
        {model ? 'Save details' : 'Add model'}
      </button>
      <button key="cancel" type="button" className="plain" onClick={onCancel}>Cancel</button>
    </>
  )

  return (
    <Drawer title={model ? 'Edit model' : forWishlist ? 'Add a kit to your wishlist' : 'Add a model'} onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="segmented hobby-picker" role="group" aria-label="Hobby">
        {lookups.hobbies.map((h) => (
          <button key={h} type="button" aria-pressed={form.hobby === h} onClick={() => pickHobby(h)}>{h}</button>
        ))}
      </div>
      {!model && maker && (
        <section className="panel-section">
          <span className="field-label">Look up a kit (optional)</span>
          {makers.length > 1 && (
            <div className="segmented maker" role="group" aria-label="Kit maker">
              {makers.map((m) => (
                <button key={m} type="button" aria-pressed={maker === m}
                  onClick={() => { setMaker(m); setFound(null); setChoices(null) }}>{m}</button>
              ))}
            </div>
          )}
          {maker === 'Bandai' && <p className="hint">Bandai kits are looked up on hlj.com (HobbyLink Japan).</p>}
          {maker === 'Games Workshop' && <p className="hint">Warhammer kits are looked up at Good Games (goodgames.com.au).</p>}
          <div className="lookup-row">
            <label className="field">
              <span className="field-label">{LOOKUP_HELP[maker].label}</span>
              <input value={kitCode} onChange={(e) => setKitCode(e.target.value)}
                placeholder={LOOKUP_HELP[maker].example} autoCapitalize={['Bandai', 'Games Workshop'].includes(maker) ? 'none' : 'characters'}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookup() } }} />
            </label>
            <button type="button" className="secondary" onClick={() => lookup()} disabled={busy || !kitCode.trim()}>
              {busy ? 'Looking up...' : 'Look up'}
            </button>
            {['Bandai', 'Games Workshop'].includes(maker) && (
              <ScanButton className="secondary" label="Scan the box"
                onBarcode={(barcode) => { setKitCode(barcode); return lookup(barcode) }} />
            )}
          </div>
          {choices && (
            <>
              <p className="hint">{choices.length} kits match. Which one?</p>
              <ul className="list kit-choices">
                {choices.map((c) => (
                  <li key={c.key}>
                    <button type="button" className="row-button" onClick={() => { setKitCode(c.title); lookup(c.code) }}>
                      {c.thumb_url
                        ? <img className="thumb" src={c.thumb_url} alt="" referrerPolicy="no-referrer" loading="lazy" />
                        : <span className="thumb thumb-empty" aria-hidden="true" />}
                      <span>{c.title}{c.note && <span className="muted small"> · {c.note}</span>}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {found && (
            <div className="preview">
              {found.has_image ? <img src={imageUrl(found)} alt="" /> : <div className="photo-missing">No photo</div>}
              <p className="preview-title">{found.title}</p>
            </div>
          )}
        </section>
      )}
      <form id="model-form" onSubmit={submit}>
        <fieldset>
          <legend>Kit</legend>
          <Field label="Model name" required wide>
            <input value={form.name} onChange={set('name')} required placeholder={example.name} />
          </Field>
          <Field label="Brand">
            <select value={form.brand_id} onChange={set('brand_id')}>
              <option value="">—</option>
              {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              {form.brand_id.startsWith(NEW_BRAND) && (
                <option value={form.brand_id}>{form.brand_id.slice(NEW_BRAND.length)} (new)</option>
              )}
            </select>
          </Field>
          <Field label="Kit code" hint="Needed for a photo">
            <input value={form.product_code} onChange={set('product_code')} placeholder={example.code} />
          </Field>
          <Field label="Scale">
            <input value={form.scale} onChange={set('scale')} placeholder={example.scale} />
          </Field>
          {form.hobby === 'Gundam' && (
            <Field label="Grade" hint="HG, RG, MG, PG, SD...">
              <input value={form.grade} onChange={setGrade} list="gundam-grades" placeholder="e.g. HG" autoCapitalize="characters" />
              <datalist id="gundam-grades">
                {Object.keys(lookups.gundam_grades).map((g) => <option key={g} value={g} />)}
              </datalist>
            </Field>
          )}
          {form.hobby === 'Warhammer' && (
            <>
              <Field label="Army">
                <input value={form.faction} onChange={set('faction')} placeholder="e.g. Ultramarines" />
              </Field>
              <Field label="Minis in the box">
                <input type="number" min="1" step="1" inputMode="numeric" value={form.figures} onChange={set('figures')} />
              </Field>
            </>
          )}
          <Field label="Status">
            <select value={form.status} onChange={set('status')}>
              {lookups.model_statuses.map((s) => <option key={s}>{s}</option>)}
            </select>
          </Field>
          {form.hobby !== 'Warhammer' && (
            <Field label="Scalemates link" wide hint="Paste the kit's page address from scalemates.com">
              <input type="url" value={form.scalemates_url} onChange={set('scalemates_url')}
                placeholder="https://www.scalemates.com/kits/..." />
            </Field>
          )}
        </fieldset>
        {!wanted && (
          <fieldset>
            <legend>Stash</legend>
            <Field label="Price paid ($)">
              <input type="number" min="0" step="0.01" inputMode="decimal" value={form.price_paid} onChange={set('price_paid')} />
            </Field>
            <Field label="Bought on">
              <input type="date" value={form.purchase_date} onChange={set('purchase_date')} />
            </Field>
            <Field label="Bought from" wide>
              <input value={form.purchased_from} onChange={set('purchased_from')} placeholder="e.g. Hobbyrama" />
            </Field>
            {model && (
              <>
                <Field label="Started"><input type="date" value={form.started_on} onChange={set('started_on')} /></Field>
                <Field label="Finished"><input type="date" value={form.finished_on} onChange={set('finished_on')} /></Field>
              </>
            )}
          </fieldset>
        )}
      </form>
    </Drawer>
  )
}
