import { useEffect, useState } from 'react'
import { api, money, shortDate } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { buttonHref, readSent } from './bunningsButton.js'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { SproutIcon } from '../../components/icons.jsx'
import { SowMonths, plantEmoji, useGardenLists } from './gardenParts.jsx'

// The plant guide: what grows well in pots, filtered to what you can sow now / next month in your
// climate, by kind, or searched. Each card: light, water, pot size, days to harvest, the sowing months,
// and which of your spaces get enough light for it.
export function GuideView() {
  const { refreshKey, openPanel } = useApp()
  const lists = useGardenLists().data
  const [season, setSeason] = useState('now')
  const [kind, setKind] = useState('')
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.gardenGuides({ season: q ? '' : season, kind, q }).then(setData).catch((e) => setError(e.message)), q ? 250 : 0)
    return () => clearTimeout(t)
  }, [season, kind, q, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  const climate = data?.climate?.toLowerCase()
  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the guide..." aria-label="Search the guide" />
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind">
          <option value="">Every kind</option>
          {(lists?.guide_kinds ?? []).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <button type="button" className="secondary" onClick={() => openPanel('gguidenew', {})}>+ Your own</button>
      </div>
      <div className="chip-row" role="group" aria-label="When">
        {[['now', `Sow in ${data?.month ?? 'this month'}`], ['next', 'Next month'], ['', 'All']].map(([v, l]) => (
          <button key={v} type="button" className="chip-filter" aria-pressed={season === v} disabled={!!q} onClick={() => setSeason(v)}>{l}</button>
        ))}
      </div>
      {data && <p className="muted small">For a {climate} climate (change it under Today → Garden settings). Months are a guide - local spots vary.</p>}
      {!data ? <p className="muted loading">Loading...</p> : data.guides.length === 0 ? <p className="empty card">Nothing matches that.</p> : (
        <ul className="garden-guide-grid">
          {data.guides.map((g) => (
            <li key={g.guide_id}>
              <button type="button" className="card garden-guide-card" onClick={() => openPanel('gguide', { id: g.guide_id })}>
                <span className="garden-guide-top">
                  <span className="garden-guide-emoji" aria-hidden="true">{plantEmoji({ name: g.name, kind: g.kind })}</span>
                  <span className="grow">
                    <span className="item-title">{g.name}</span>
                    <span className="item-meta">{g.kind}{g.custom && ' · yours'}{g.growing > 0 && ` · ${g.growing} growing`}</span>
                  </span>
                  {g.sow_now ? <span className="pill ok">Sow now</span> : g.sow_next ? <span className="pill low">Next month</span> : null}
                </span>
                <SowMonths months={g.sow_months} />
                <span className="item-meta">{[g.sun, `water ${g.water.toLowerCase()}`, g.pot_min_l && `${g.pot_min_l} L+ pot`,
                  g.days_min && `${g.days_min}–${g.days_max} days`].filter(Boolean).join(' · ')}</span>
                <span className={`small ${g.fits_spaces.length ? 'garden-fits' : 'muted'}`}>
                  {g.fits_spaces.length ? `Suits ${g.fits_spaces.join(', ')}` : `Needs ${g.sun_hours_min}+ h of sun`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Supplies and the seed bank: add from a Bunnings link (or search Bunnings in your browser), by hand;
// wanted ones go on the Wishlist (under Bunnings when they came from there).
const ORDER = ['Wanted', 'Running low', 'Have', 'Used up']
export function SuppliesView() {
  const { refreshKey, openPanel, changed, showToast } = useApp()
  const [items, setItems] = useState(null)
  const [link, setLink] = useState('')
  const [status, setStatus] = useState('Have')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.gardenItems().then(setItems).catch((e) => setError(e.message)) }, [refreshKey])
  const isLink = /bunnings\.com\.au\/.+_p\d+/i.test(link)
  const add = async (e) => {
    e.preventDefault()
    if (!isLink) {
      window.open(`https://www.bunnings.com.au/search/products?q=${encodeURIComponent(link.trim())}`, '_blank', 'noopener,noreferrer')
      return
    }
    setBusy(true)
    setError('')
    try {
      const item = await api.addGardenItemFromBunnings({ url: link, status })
      setLink('')
      changed()
      showToast(item.existing ? `You already have ${item.name}`
        : item.partial ? `Added ${item.name} - Bunnings only shows plants to stores that sell them, so add the price yourself`
          : `Added ${item.name}${item.price != null ? ` (${money(item.price)})` : ''}`)
      openPanel('gitem', { id: item.item_id })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  const [sent, setSent] = useState(() => readSent(window.location.hash))
  const seeds = items?.filter((i) => i.kind === 'Seeds') ?? []
  const others = items?.filter((i) => i.kind !== 'Seeds') ?? []
  const wantedTotal = others.concat(seeds).filter((i) => i.status === 'Wanted').reduce((a, i) => a + (i.price ?? 0), 0)
  return (
    <section className="page">
      {sent && <SentFromBunnings sent={sent} onDone={() => { setSent(null); window.history.replaceState(null, '', window.location.pathname) }} />}
      <form className="card garden-bunnings" onSubmit={add}>
        <label className="field grow">Bunnings link - or words to search Bunnings for
          <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.bunnings.com.au/..._p1234567  or  'potting mix'" />
        </label>
        {isLink && (
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="I">
            <option value="Have">I have it</option>
            <option value="Wanted">I want it</option>
          </select>
        )}
        <button type="submit" className="primary" disabled={busy || !link.trim()}>{busy ? 'Reading Bunnings...' : isLink ? 'Add from Bunnings' : 'Search Bunnings ↗'}</button>
        <p className="muted small garden-bunnings-help">Find it on Bunnings (the search opens their site), copy the product's link - or Share it from
          their app - and paste it here: the name, price, photo, weight and how-to come across. Only that one page is read.</p>
        {error && <p className="alert error small">{error}</p>}
        <BunningsButton />
      </form>
      <div className="toolbar">
        <p className="summary grow">{items ? <><strong>{items.length}</strong> item{items.length === 1 ? '' : 's'}</> : ''}
          {wantedTotal > 0 && <span className="muted"> · wanted ones about {money(wantedTotal)}</span>}</p>
        <button type="button" className="secondary" onClick={() => openPanel('gitem', {})}>+ Add by hand</button>
      </div>
      {!items ? <p className="muted loading">Loading...</p> : items.length === 0 ? (
        <EmptyState Icon={SproutIcon} title="No supplies yet">Potting mix, fertiliser, pots, seed packets... paste a Bunnings link above,
          or add them by hand.</EmptyState>
      ) : (
        <>
          {ORDER.map((s) => {
            const list = others.filter((i) => i.status === s)
            return list.length > 0 && (
              <section key={s} className="card home-card garden-group">
                <h2 className="home-card-title">{s}</h2>
                <ul className="list plain-list">{list.map((i) => <ItemRow key={i.item_id} i={i} />)}</ul>
              </section>
            )
          })}
          {seeds.length > 0 && (
            <section className="card home-card garden-group">
              <h2 className="home-card-title">Seed bank</h2>
              <ul className="list plain-list">{seeds.map((i) => <ItemRow key={i.item_id} i={i} />)}</ul>
            </section>
          )}
        </>
      )}
    </section>
  )
}

// What the "Send to Off the Clock" button brought from a Bunnings page: a look before it's saved.
function SentFromBunnings({ sent, onDone }) {
  const { changed, openPanel, showToast } = useApp()
  const [status, setStatus] = useState('Have')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const item = await api.addGardenItemFromPage({ page: sent, status })
      changed()
      showToast(item.existing ? `Updated ${item.name}${item.price_before != null && item.price !== item.price_before
        ? ` (${money(item.price_before)} → ${money(item.price)})` : ''}` : `Added ${item.name}`)
      onDone()
      openPanel('gitem', { id: item.item_id })
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const store = sent.store_name || (sent.store_code ? `store ${sent.store_code}` : '')
  const stock = sent.stock?.msg === 'notSoldAtThisStore' ? 'not sold at this store' : sent.stock?.color === 'GREEN' ? 'in stock'
    : ['AMBER', 'ORANGE', 'YELLOW'].includes(sent.stock?.color) ? 'low stock' : sent.stock?.color === 'RED' ? 'out of stock' : ''
  return (
    <section className="card garden-sent" aria-label="From Bunnings">
      {sent.image?.startsWith('https://media.bunnings.com.au/') && <img src={`${sent.image}&t=w1200`} alt="" referrerPolicy="no-referrer" />}
      <div className="grow">
        <p className="muted small">From Bunnings{store && ` · ${store}`}</p>
        <h2 className="home-card-title">{sent.name}</h2>
        <p className="small">{[sent.price != null && money(sent.price), stock && `${stock}${store ? ` at ${store}` : ''}`, `I/N ${sent.item}`]
          .filter(Boolean).join(' · ')}</p>
        {error && <p className="alert error small">{error}</p>}
        <div className="button-row">
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="I">
            <option value="Have">I have it</option>
            <option value="Wanted">I want it</option>
          </select>
          <button type="button" className="primary" disabled={busy} onClick={save}>{busy ? 'Saving...' : 'Save'}</button>
          <button type="button" className="plain" onClick={onDone}>Not now</button>
        </div>
      </div>
    </section>
  )
}

// Setting the button up: drag it to the bookmarks bar (a computer), or copy it into a bookmark (a phone).
function BunningsButton() {
  const href = buttonHref(window.location.origin)
  const [copied, setCopied] = useState(false)
  // React won't render a javascript: address (a safety rule), so it's set on the link directly - as the link
  // appears (it's inside a fold, so it isn't there when this first runs).
  const link = (el) => el?.setAttribute('href', href)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(href)
      setCopied(true)
    } catch {
      window.prompt('Copy this, then paste it as the bookmark\'s address:', href)
    }
  }
  return (
    <Fold title="Plants and your store's prices: the Bunnings button" className="garden-button-fold">
      <p className="small">Bunnings shows plants (and each store's price and stock) only for the store you've chosen - which the app
        can't see. This button runs in your own browser on a Bunnings product page and sends what you're looking at here.</p>
      <p className="small"><strong>On a computer:</strong> drag this to your bookmarks bar →{' '}
        <a ref={link} className="button secondary small garden-button-link" onClick={(e) => { e.preventDefault(); showHow() }}
          draggable="true">Send to Off the Clock</a></p>
      <p className="small"><strong>On an Android phone (Chrome):</strong> <button type="button" className="secondary small" onClick={copy}>
        {copied ? 'Copied ✓' : 'Copy the button'}</button> then bookmark any page, edit the bookmark: name it <em>Send to Off the Clock</em> and paste
        over its address. To use it: on a Bunnings product page, tap the address bar, type <em>Send to</em> and tap the bookmark (the one with
        the star).</p>
      <p className="muted small">Make it on each device you use (it remembers this app's address as that device sees it:
        {' '}{window.location.origin}). Choose your store on Bunnings first.</p>
    </Fold>
  )
}
const showHow = () => window.alert('Drag this button to your bookmarks bar (it does nothing here). Then, on a Bunnings product page, click the bookmark.')

function ItemRow({ i }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button" onClick={() => openPanel('gitem', { id: i.item_id })}>
        {i.photo_url ? <img className="thumb" src={i.photo_url} alt="" loading="lazy" /> : <span className="garden-emoji" aria-hidden="true">{i.kind === 'Seeds' ? '🌱' : '🧺'}</span>}
        <span className="grow">
          <span className="item-title">{i.name}</span>
          <span className="item-meta">{[i.kind, i.brand, i.qty != null && `${i.qty} left`, i.guide_name,
            i.sow_by && (i.expired ? `past sow-by (${shortDate(i.sow_by)})` : `sow by ${shortDate(i.sow_by)}`), i.bunnings_item && 'Bunnings'].filter(Boolean).join(' · ')}</span>
        </span>
        {i.price != null && <span className="small">{money(i.price)}</span>}
        {i.kind === 'Seeds' && i.status !== 'Have' && <span className="pill">{i.status}</span>}
      </button>
    </li>
  )
}
