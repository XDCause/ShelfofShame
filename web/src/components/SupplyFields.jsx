import { today } from '../api.js'

// The supply form fields, shared by "Add a supply" and an item's "Edit details".
// `form` holds strings (what inputs hold); `set(name)` returns the change handler.

export const FIELDS = [
  'brand_id', 'product_code', 'name', 'category_id', 'paint_type', 'finish', 'size',
  'qty_on_hand', 'reorder_at', 'condition', 'unit_price', 'purchase_date', 'purchased_from',
  'location_id', 'notes',
]
const INTEGER_FIELDS = ['brand_id', 'category_id', 'location_id', 'qty_on_hand', 'reorder_at']

// New items start with your usual conventions: 1 on hand, reorder at 0, sealed, bought today
// from your default shop.
export function emptyForm(lookups, settings = {}) {
  const other = lookups.locations.find((l) => l.name === 'Other')
  return {
    ...Object.fromEntries(FIELDS.map((f) => [f, ''])),
    qty_on_hand: '1',
    reorder_at: '0',
    condition: 'Sealed',
    purchase_date: today(),
    purchased_from: settings.default_shop ?? '',
    location_id: other ? String(other.id) : '',
  }
}

export const toForm = (supply) =>
  Object.fromEntries(FIELDS.map((f) => [f, supply[f] == null ? '' : String(supply[f])]))

// Only the listed fields; '' becomes null; ids and counts become numbers; price stays a
// string so the cents are exact.
export function toPayload(form, fields = FIELDS) {
  return Object.fromEntries(fields.map((f) => {
    const v = (form[f] ?? '').trim()
    if (v === '') return [f, null]
    return [f, INTEGER_FIELDS.includes(f) ? Number(v) : v]
  }))
}

// Fill fields from a scan or Tamiya lookup result (`suggested` = best-guess values).
export function applyResult(f, r) {
  const s = r.suggested ?? {}
  return {
    ...f,
    brand_id: r.brand_id != null ? String(r.brand_id) : f.brand_id,
    product_code: r.product_code ?? f.product_code,
    name: s.name ?? f.name,
    category_id: s.category_id != null ? String(s.category_id) : f.category_id,
    paint_type: s.paint_type ?? f.paint_type,
    finish: s.finish ?? f.finish,
    size: s.size ?? f.size,
    // the usual price (Acrylic Minis, panel lines...) unless you've typed one. Form fields are
    // text, and the API sends the price as a number.
    ...('unit_price' in f && { unit_price: f.unit_price || String(s.est_price ?? '') }),
    ...('est_price' in f && { est_price: f.est_price || String(s.est_price ?? '') }),
  }
}

// What the item is - the fields you rarely change after adding it.
export const DETAIL_FIELDS = ['name', 'category_id', 'brand_id', 'product_code', 'paint_type',
  'finish', 'size', 'unit_price', 'reorder_at']

// stock: also show the stock fields (when adding). reorder: show "Reorder at" with the item
// fields (when editing details - it's rarely changed, so it lives there, not in quick settings).
export default function SupplyFields({ form, set, lookups, stock = false, reorder = false }) {
  return (
    <>
      <fieldset>
        <legend>Item</legend>
        <Field label="Name / colour" required wide>
          <input value={form.name} onChange={set('name')} required placeholder="e.g. Acrylic XF1 Flat Black" />
        </Field>
        <Field label="Category" required>
          <select value={form.category_id} onChange={set('category_id')} required>
            <option value="">Choose...</option>
            {lookups.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Brand">
          <select value={form.brand_id} onChange={set('brand_id')}>
            <option value="">—</option>
            {lookups.brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </Field>
        <Field label="Product code">
          <input value={form.product_code} onChange={set('product_code')} placeholder="e.g. T81701" />
        </Field>
        <Field label="Size">
          <input value={form.size} onChange={set('size')} placeholder="e.g. 10ml, 18m" />
        </Field>
        <Field label="Paint type">
          <Choice value={form.paint_type} onChange={set('paint_type')} options={lookups.paint_types} />
        </Field>
        <Field label="Finish">
          <Choice value={form.finish} onChange={set('finish')} options={lookups.finishes} />
        </Field>
        <Field label="Price ($)">
          <input type="number" min="0" step="0.01" inputMode="decimal" value={form.unit_price} onChange={set('unit_price')} />
        </Field>
        {reorder && <ReorderField form={form} set={set} />}
      </fieldset>

      {stock && (
        <fieldset>
          <legend>Stock</legend>
          <Field label="Quantity">
            <input type="number" min="0" step="1" inputMode="numeric" value={form.qty_on_hand} onChange={set('qty_on_hand')} />
          </Field>
          <Field label="Condition">
            <Choice value={form.condition} onChange={set('condition')} options={lookups.conditions} />
          </Field>
          <ReorderField form={form} set={set} />
          <Field label="Location">
            <select value={form.location_id} onChange={set('location_id')}>
              <option value="">—</option>
              {lookups.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </Field>
          <Field label="Last purchased">
            <input type="date" value={form.purchase_date} onChange={set('purchase_date')} />
          </Field>
          <Field label="Last bought from">
            <input value={form.purchased_from} onChange={set('purchased_from')} placeholder="e.g. Hobbyrama" />
          </Field>
          <Field label="Notes" wide>
            <textarea rows="2" value={form.notes} onChange={set('notes')} />
          </Field>
        </fieldset>
      )}
    </>
  )
}

function ReorderField({ form, set }) {
  return (
    <Field label="Reorder at" hint="Low when quantity drops to this (0 = only when your last one runs low)">
      <input type="number" min="0" step="1" inputMode="numeric" value={form.reorder_at} onChange={set('reorder_at')} />
    </Field>
  )
}

export function Field({ label, required, hint, wide, children }) {
  return (
    <label className={wide ? 'field wide' : 'field'}>
      <span className="field-label">
        {label}
        {required && <span className="req" aria-hidden="true"> *</span>}
      </span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

export function Choice({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange}>
      <option value="">—</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}
