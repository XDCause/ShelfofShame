import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { LogoMark } from '../../components/icons.jsx'
import Landscape from '../../components/Landscape.jsx'
import { cancelled, passkeysWork, getPasskey } from './passkeys.js'

// The app only shows once this device is signed in (api/app/auth.py). Signed out at any point - the 30 days are
// up, or it was signed out from another device - any request answers 401 (api.js) and this shows the sign-in again.
export default function AuthGate({ children }) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const check = useCallback(() => {
    api.authStatus().then((s) => { setStatus(s); setError('') }).catch((e) => setError(`Can't reach the app: ${e.message}`))
  }, [])
  useEffect(() => {
    check()
    const signedOut = () => setStatus((s) => (s ? { ...s, signed_in: false } : s))
    window.addEventListener('otc-signed-out', signedOut)
    return () => window.removeEventListener('otc-signed-out', signedOut)
  }, [check])
  if (error) return <SignInFrame><p className="alert error" role="alert">{error}</p></SignInFrame>
  if (!status) return <SignInFrame><p className="muted">Loading...</p></SignInFrame>
  if (!status.signed_in) return <SignIn status={status} onSignedIn={check} />
  return children
}

function SignInFrame({ children }) {
  return (
    <main className="signin">
      <div className="signin-art" aria-hidden="true"><Landscape scene="peaks" seed={3} hue="#84a85c" /></div>
      <section className="signin-card" aria-labelledby="signin-title">
        <p className="signin-brand"><LogoMark size={30} /> Off the Clock</p>
        {children}
      </section>
    </main>
  )
}

// The password (then, with an authenticator, its code), or a passkey.
function SignIn({ status, onSignedIn }) {
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [needCode, setNeedCode] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const codeInput = useRef(null)
  useEffect(() => { if (needCode) codeInput.current?.focus() }, [needCode])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await api.signIn(password, needCode ? code : null)
      if (r.need_code) setNeedCode(true)
      else onSignedIn()
    } catch (err) {
      setError(err.message)
      if (needCode) setCode('')
    } finally {
      setBusy(false)
    }
  }
  const passkey = async () => {
    setBusy(true)
    setError('')
    try {
      await api.passkeySignIn(await getPasskey(await api.passkeyLoginOptions()))
      onSignedIn()
    } catch (err) {
      if (!cancelled(err)) setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!status.set_up) {
    return (
      <SignInFrame>
        <h1 id="signin-title" className="signin-title">Set a password first</h1>
        <p>There's no password yet. On the PC, in the app's folder, run:</p>
        <pre className="signin-command">.\set-password.ps1</pre>
        <p className="muted small">Then come back here and sign in. (It's set on the PC on purpose: nobody else on the
          Wi-Fi can get here first.)</p>
        <button type="button" className="secondary" onClick={onSignedIn}>I've set it</button>
      </SignInFrame>
    )
  }
  return (
    <SignInFrame>
      <h1 id="signin-title" className="signin-title">{needCode ? 'One more step' : 'Welcome back'}</h1>
      <form className="signin-form" onSubmit={submit}>
        {!needCode ? (
          <label className="field">
            <span className="field-label">Password</span>
            <input type="password" autoComplete="current-password" value={password} autoFocus required
              onChange={(e) => setPassword(e.target.value)} />
          </label>
        ) : (
          <label className="field">
            <span className="field-label">The 6-digit code from your authenticator app</span>
            <input ref={codeInput} inputMode="numeric" autoComplete="one-time-code" value={code} required maxLength={20}
              onChange={(e) => setCode(e.target.value)} aria-describedby="signin-code-hint" />
            <span id="signin-code-hint" className="hint">Lost your phone? A recovery code works here too (each one once).</span>
          </label>
        )}
        {error && <p className="alert error small" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>{busy ? 'Signing in...' : needCode ? 'Check the code' : 'Sign in'}</button>
        {needCode && <button type="button" className="plain small" onClick={() => { setNeedCode(false); setCode(''); setError('') }}>Back</button>}
      </form>
      {!needCode && status.passkeys !== 0 && passkeysWork(status) && (
        <>
          <p className="signin-or"><span>or</span></p>
          <button type="button" className="secondary signin-passkey" onClick={passkey} disabled={busy}>Sign in with a passkey</button>
        </>
      )}
      {!needCode && !passkeysWork(status) && (
        <p className="hint">Passkeys work at the app's name (https://&lt;this PC&gt;.local), not an IP address.</p>
      )}
    </SignInFrame>
  )
}
