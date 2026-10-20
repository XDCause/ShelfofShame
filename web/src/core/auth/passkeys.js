// Passkeys in the browser (WebAuthn). The API sends options as JSON with binary fields in base64url (py_webauthn's
// options_to_json); the browser wants ArrayBuffers in and gives ArrayBuffers back, which go back as base64url.

const toBytes = (b64url) => {
  const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(b64url.length / 4) * 4, '=')
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer
}
const toB64url = (buffer) => btoa(String.fromCharCode(...new Uint8Array(buffer)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

// Can this browser, at this address, use passkeys? (Not at a bare IP address, and only over https.)
export const passkeysWork = (status) => Boolean(window.PublicKeyCredential && window.isSecureContext && status?.passkey_name)

// Make a passkey (Settings > Security): the device asks for your face / fingerprint / PIN.
export async function createPasskey(options) {
  const credential = await navigator.credentials.create({
    publicKey: {
      ...options,
      challenge: toBytes(options.challenge),
      user: { ...options.user, id: toBytes(options.user.id) },
      excludeCredentials: (options.excludeCredentials ?? []).map((c) => ({ ...c, id: toBytes(c.id) })),
    },
  })
  return {
    id: credential.id, rawId: toB64url(credential.rawId), type: credential.type,
    response: {
      clientDataJSON: toB64url(credential.response.clientDataJSON),
      attestationObject: toB64url(credential.response.attestationObject),
      transports: credential.response.getTransports?.() ?? [],
    },
  }
}

// Sign in with a passkey: the device offers the passkeys it has for this app.
export async function getPasskey(options) {
  const credential = await navigator.credentials.get({
    publicKey: {
      ...options,
      challenge: toBytes(options.challenge),
      allowCredentials: (options.allowCredentials ?? []).map((c) => ({ ...c, id: toBytes(c.id) })),
    },
  })
  return {
    id: credential.id, rawId: toB64url(credential.rawId), type: credential.type,
    response: {
      clientDataJSON: toB64url(credential.response.clientDataJSON),
      authenticatorData: toB64url(credential.response.authenticatorData),
      signature: toB64url(credential.response.signature),
      userHandle: credential.response.userHandle ? toB64url(credential.response.userHandle) : null,
    },
  }
}

// "The user cancelled" isn't an error worth showing.
export const cancelled = (e) => e?.name === 'NotAllowedError' || e?.name === 'AbortError'
