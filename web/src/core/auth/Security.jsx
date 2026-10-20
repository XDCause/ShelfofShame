import { useCallback, useEffect, useState } from 'react'
import { api, timeAgo } from '../../api.js'
import { cancelled, createPasskey, passkeysWork } from './passkeys.js'

// Settings > Security: sign out, the password, the authenticator app (and recovery codes), passkeys, signed-in devices.
export default function Security() {
  const [status, setStatus] = useState(null)
  const reload = useCallback(() => api.authStatus().then(setStatus).catch(() => {}), [])
  useEffect(() => { reload() }, [reload])
  if (!status) return <p className="muted small">Loading...</p>
  return (
    <div className="security">
      <button type="button" className="secondary" onClick={async () => { await api.signOut(); window.location.assign('/') }}>
        Sign out of this device</button>
      <Password />
      <Authenticator on={status.totp_on} onChanged={reload} />
      <Passkeys status={status} onChanged={reload} />
      <Devices />
    </div>
  )
}

function Section({ title, children }) {
  return <section className="security-part"><h3 className="section-title">{title}</h3>{children}</section>
}

function Password() {
  const [f, setF] = useState({ current: '', next: '', again: '' })
  const [msg, setMsg] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async (e) => {
    e.preventDefault()
    if (f.next !== f.again) { setMsg(['error', "The new passwords don't match."]); return }
    try {
      await api.changePassword(f.current, f.next)
      setF({ current: '', next: '', again: '' })
      setMsg(['ok', 'Password changed. Your other devices are signed out.'])
    } catch (err) {
      setMsg(['error', err.message])
    }
  }
  return (
    <Section title="Password">
      <form className="security-form" onSubmit={save}>
        <label className="field"><span className="field-label">Current password</span>
          <input type="password" autoComplete="current-password" value={f.current} onChange={set('current')} required /></label>
        <label className="field"><span className="field-label">New password</span>
          <input type="password" autoComplete="new-password" minLength={12} value={f.next} onChange={set('next')} required
            aria-describedby="pw-hint" /></label>
        <label className="field"><span className="field-label">New password again</span>
          <input type="password" autoComplete="new-password" minLength={12} value={f.again} onChange={set('again')} required /></label>
        <p id="pw-hint" className="hint">At least 12 characters - a few unrelated words together are strong and easy to remember.</p>
        {msg && <p className={`alert small ${msg[0]}`} role="status">{msg[1]}</p>}
        <button type="submit" className="secondary">Change password</button>
      </form>
    </Section>
  )
}

function Authenticator({ on, onChanged }) {
  const [step, setStep] = useState(null)        // null | 'password' | {secret, uri, qr_svg} | {codes}
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [left, setLeft] = useState(null)
  useEffect(() => { if (on) api.recoveryCodesLeft().then(setLeft).catch(() => {}) }, [on])
  const go = (work) => async (e) => {
    e?.preventDefault()
    setError('')
    try { await work() } catch (err) { setError(err.message) }
  }
  const codes = step?.codes
  return (
    <Section title="Authenticator app">
      {codes ? (
        <div className="recovery-codes">
          <p><strong>Your recovery codes.</strong> Each signs in once if you lose your phone. Keep them somewhere safe (a
            password manager, or printed) - they won't be shown again.</p>
          <ul className="recovery-list">{codes.map((c) => <li key={c} className="mono">{c}</li>)}</ul>
          <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(codes.join('\n'))}>Copy them</button>
          <button type="button" className="plain" onClick={() => setStep(null)}>I've saved them</button>
        </div>
      ) : step?.secret ? (
        <form className="security-form" onSubmit={go(async () => {
          const r = await api.totpConfirm(code)
          setCode('')
          setStep({ codes: r.recovery_codes })
          onChanged()
        })}>
          <p className="small">Scan this with an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password...),
            then type the 6-digit code it shows.</p>
          {/* the QR code is an SVG the API drew (segno) from the secret: our own markup, not anyone else's */}
          <div className="totp-qr" role="img" aria-label="QR code for the authenticator app" dangerouslySetInnerHTML={{ __html: step.qr_svg }} />
          <details className="small"><summary>Can't scan? Type this key instead</summary><p className="mono totp-secret">{step.secret}</p></details>
          <label className="field"><span className="field-label">Code from the app</span>
            <input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} required /></label>
          {error && <p className="alert error small" role="alert">{error}</p>}
          <div className="button-row"><button type="submit" className="primary">Turn it on</button>
            <button type="button" className="plain" onClick={() => setStep(null)}>Cancel</button></div>
        </form>
      ) : step === 'password' || step === 'off' || step === 'new-codes' ? (
        <form className="security-form" onSubmit={go(async () => {
          if (step === 'password') setStep(await api.totpStart(password))
          else if (step === 'off') { await api.totpOff(password, code); setStep(null); onChanged() }
          else setStep({ codes: (await api.newRecoveryCodes(password)).recovery_codes })
          setPassword('')
          setCode('')
        })}>
          <label className="field"><span className="field-label">Your password</span>
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          {step === 'off' && <label className="field"><span className="field-label">A code from the app (or a recovery code)</span>
            <input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} required /></label>}
          {error && <p className="alert error small" role="alert">{error}</p>}
          <div className="button-row"><button type="submit" className={step === 'off' ? 'danger' : 'primary'}>
            {step === 'password' ? 'Next' : step === 'off' ? 'Turn it off' : 'Make new codes'}</button>
            <button type="button" className="plain" onClick={() => { setStep(null); setError('') }}>Cancel</button></div>
        </form>
      ) : on ? (
        <>
          <p className="small"><span className="pill ok">On</span> Signing in with your password also asks for its code.
            {left && ` ${left.unused} of ${left.total} recovery codes unused.`}</p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={() => setStep('new-codes')}>New recovery codes</button>
            <button type="button" className="plain destructive" onClick={() => setStep('off')}>Turn it off</button>
          </div>
        </>
      ) : (
        <>
          <p className="small">Off. With it on, a stolen password isn't enough: signing in also needs the code on your phone.</p>
          <button type="button" className="primary" onClick={() => setStep('password')}>Set up an authenticator app</button>
        </>
      )}
    </Section>
  )
}

function Passkeys({ status, onChanged }) {
  const [keys, setKeys] = useState(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const reload = useCallback(() => api.passkeys().then(setKeys).catch((e) => setError(e.message)), [])
  useEffect(() => { reload() }, [reload])
  const add = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.passkeyRegister(await createPasskey(await api.passkeyRegisterOptions()), name.trim() || 'Passkey')
      setName('')
      reload()
      onChanged()
    } catch (err) {
      if (!cancelled(err)) setError(err.message)
    }
  }
  return (
    <Section title="Passkeys">
      <p className="small">Sign in with your face, fingerprint or device PIN instead of the password - nothing to type or
        steal. Each device's passkey works at the address it was made on.</p>
      {keys?.length > 0 && (
        <ul className="list compact security-list">
          {keys.map((k) => (
            <li key={k.passkey_id}>
              <span className="grow"><span className="item-title">{k.name}</span>
                <span className="item-meta">{k.rp_id} · made {timeAgo(k.created_at)}{k.last_used_at && ` · used ${timeAgo(k.last_used_at)}`}</span></span>
              <button type="button" className="plain small destructive" onClick={async () => {
                if (!window.confirm(`Remove the passkey "${k.name}"? That device will need the password again.`)) return
                await api.removePasskey(k.passkey_id).catch((err) => setError(err.message))
                reload()
                onChanged()
              }}>Remove</button>
            </li>
          ))}
        </ul>
      )}
      {passkeysWork(status) ? (
        <form className="toolbar" onSubmit={add}>
          <input className="grow" value={name} onChange={(e) => setName(e.target.value)} maxLength={60}
            placeholder="This device's name (e.g. My phone)" aria-label="Passkey name" />
          <button type="submit" className="secondary">Add a passkey</button>
        </form>
      ) : (
        <p className="hint">To add one, open the app at https://&lt;this PC's name&gt;.local - passkeys don't work at an IP address.</p>
      )}
      {error && <p className="alert error small" role="alert">{error}</p>}
    </Section>
  )
}

// "Chrome on Windows" from a browser's user-agent string (roughly: it's only a hint).
function deviceName(ua = '') {
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'A browser'
  const system = /iPhone|iPad/.test(ua) ? 'iPhone / iPad' : /Android/.test(ua) ? 'Android' : /Windows/.test(ua) ? 'Windows'
    : /Mac OS/.test(ua) ? 'Mac' : /Linux/.test(ua) ? 'Linux' : ''
  return system ? `${browser} on ${system}` : browser
}

function Devices() {
  const [list, setList] = useState(null)
  const [error, setError] = useState('')
  const reload = useCallback(() => api.devices().then(setList).catch((e) => setError(e.message)), [])
  useEffect(() => { reload() }, [reload])
  return (
    <Section title="Signed-in devices">
      {list && (
        <ul className="list compact security-list">
          {list.map((d) => (
            <li key={d.session_id}>
              <span className="grow"><span className="item-title">{deviceName(d.user_agent)}{d.this_device && <span className="pill ok"> This device</span>}</span>
                <span className="item-meta">{d.method === 'passkey' ? 'passkey' : 'password'} · {d.ip} · last seen {timeAgo(d.last_seen_at)}</span></span>
              {!d.this_device && <button type="button" className="plain small destructive" onClick={async () => {
                await api.signOutDevice(d.session_id).catch((err) => setError(err.message))
                reload()
              }}>Sign out</button>}
            </li>
          ))}
        </ul>
      )}
      {list?.length > 1 && <button type="button" className="secondary" onClick={async () => {
        await api.signOutOthers().catch((err) => setError(err.message))
        reload()
      }}>Sign out every other device</button>}
      {error && <p className="alert error small" role="alert">{error}</p>}
      <p className="hint">Each device stays signed in for 30 days. Lost a device and can't sign in? On the PC run
        .\set-password.ps1 -SignOutEverywhere (add -ResetAuthenticator if it was your authenticator phone).</p>
    </Section>
  )
}
