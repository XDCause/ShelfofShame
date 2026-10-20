"""Signing in: strangers get nothing; the password, the authenticator (and its recovery codes), passkeys, devices,
guessing limits, cross-site requests, expiry, and setting the password on the PC."""
import base64
import hashlib
import io
import json
import re
import secrets

import cbor2
import pyotp
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.db import db
from app.main import app
from tests.conftest import TEST_PASSWORD

PUBLIC = {("GET", "/api/health"), ("GET", "/api/about"),   # (about: just "dev" or "prod", for the badge)
          ("GET", "/api/auth/status"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout"),
          ("POST", "/api/auth/passkey/login/options"), ("POST", "/api/auth/passkey/login/verify")}
ROUTES = sorted((m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops)


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def fresh_account(password=TEST_PASSWORD):
    auth.set_password(password)


def sign_in(c, password=TEST_PASSWORD, **kw):
    return c.post("/api/auth/login", json={"password": password, **kw})


# ---------------------------------------------------------------- strangers
def test_a_stranger_gets_nothing(anon):
    """Every route but the public few refuses a device that hasn't signed in. (One test looping over the routes, not
    one per route: each test's set-up is the slow part.)"""
    fresh_account()
    wrong = []
    for method, path in ROUTES:
        if (method, path) in PUBLIC:
            continue
        url = re.sub(r"\{(\w+)\}", lambda m: "home" if m.group(1) == "area" else "1", path)   # a real-looking value for each
        r = anon.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)
        allowed = (401, 422) if path.startswith("/api/auth/") else (401,)                  # (auth: a bad body may be refused first)
        if r.status_code not in allowed:
            wrong.append(f"{method} {path}: {r.status_code} {r.text[:80]}")
    assert len(ROUTES) > 400 and not wrong, "\n".join(wrong)


def test_a_stranger_sees_only_whether_its_set_up(anon):
    assert anon.get("/api/auth/status").json() == {"set_up": False, "signed_in": False, "totp_on": False,
                                                   "passkeys": None, "passkey_name": True}
    assert sign_in(anon).status_code == 409                                     # no password yet: set it on the PC
    fresh_account()
    s = anon.get("/api/auth/status").json()
    assert s["set_up"] and not s["signed_in"] and s["passkeys"] is None         # (how many passkeys: not a stranger's business)


# ---------------------------------------------------------------- password
def test_signing_in_and_out(anon):
    fresh_account()
    assert anon.get("/api/supplies").status_code == 401
    assert sign_in(anon, "wrong password!").status_code == 401
    r = sign_in(anon)
    assert r.json() == {"signed_in": True}
    cookie = r.headers["set-cookie"].lower()
    for part in ("httponly", "secure", "samesite=strict", "max-age=2592000", "path=/"):
        assert part in cookie, part
    assert anon.get("/api/supplies").status_code == 200
    assert anon.get("/api/auth/status").json()["signed_in"]
    with db() as conn:                                                           # only the token's hash is kept
        stored = conn.execute("SELECT token_hash FROM auth_sessions").fetchall()
    assert anon.cookies.get(auth.COOKIE) not in [s["token_hash"] for s in stored]
    anon.post("/api/auth/logout")
    assert anon.get("/api/supplies").status_code == 401


def test_the_password_hash_is_argon2_never_the_password():
    fresh_account()
    with db() as conn:
        h = conn.execute("SELECT password_hash FROM auth_account").fetchone()["password_hash"]
    assert h.startswith("$argon2id$") and TEST_PASSWORD not in h


def test_guessing_is_slowed_down(anon):
    fresh_account()
    for _ in range(auth.FAILS_PER_ADDRESS):
        assert sign_in(anon, "nope nope nope").status_code == 401
    assert sign_in(anon).status_code == 429                                      # even the right one, for now
    elsewhere = TestClient(app, base_url="https://testserver", headers={"X-Real-IP": "10.0.0.99"})
    assert sign_in(elsewhere).status_code == 200                                 # another device isn't blocked...
    for i in range(auth.FAILS_EVERYWHERE):
        TestClient(app, base_url="https://testserver", headers={"X-Real-IP": f"10.9.{i}.1"}).post(
            "/api/auth/login", json={"password": "spread out guessing"})
    assert sign_in(TestClient(app, base_url="https://testserver", headers={"X-Real-IP": "10.0.0.98"})).status_code == 429   # ...until it's everywhere


def test_a_session_expires(client):
    with db() as conn:
        conn.execute("UPDATE auth_sessions SET expires_at = now() - interval '1 second'")
    assert client.get("/api/supplies").status_code == 401


def test_changing_the_password_signs_out_other_devices(client, anon):
    sign_in(anon)
    assert client.post("/api/auth/password", json={"current": "not it at all", "new": "a brand new password"}).status_code == 401
    assert client.post("/api/auth/password", json={"current": TEST_PASSWORD, "new": "short"}).status_code == 422
    assert client.post("/api/auth/password", json={"current": TEST_PASSWORD, "new": TEST_PASSWORD}).status_code == 422
    assert client.post("/api/auth/password", json={"current": TEST_PASSWORD, "new": "a brand new password"}).json() == {"changed": True}
    assert client.get("/api/supplies").status_code == 200                       # this device stays signed in
    assert anon.get("/api/supplies").status_code == 401                         # the other one doesn't
    assert sign_in(anon).status_code == 401 and sign_in(anon, "a brand new password").status_code == 200


# ---------------------------------------------------------------- cross-site requests
def test_a_change_from_another_site_is_refused(client):
    r = client.post("/api/journal", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.get("/api/supplies", headers={"Origin": "https://evil.example"}).status_code == 200   # reading is fine
    assert client.post("/api/journal", json={"title": "Mine"}, headers={"Origin": "https://testserver"}).status_code == 201


# ---------------------------------------------------------------- authenticator
def turn_on_authenticator(client):
    assert client.post("/api/auth/totp/start", json={"password": "wrong password"}).status_code == 401
    start = client.post("/api/auth/totp/start", json={"password": TEST_PASSWORD}).json()
    assert start["uri"].startswith("otpauth://totp/") and "<svg" in start["qr_svg"]
    totp = pyotp.TOTP(start["secret"])
    assert client.post("/api/auth/totp/confirm", json={"code": "000000" if totp.now() != "000000" else "111111"}).status_code == 401
    done = client.post("/api/auth/totp/confirm", json={"code": totp.now()}).json()
    assert done["totp_on"] and len(done["recovery_codes"]) == 10
    return totp, done["recovery_codes"]


def test_the_authenticator_asks_for_a_code_each_once(client, anon, monkeypatch):
    totp, recovery = turn_on_authenticator(client)
    assert anon.get("/api/auth/status").json()["totp_on"]
    assert sign_in(anon).json() == {"need_code": True}                        # the right password: now the code
    assert anon.get("/api/supplies").status_code == 401
    assert sign_in(anon, code="123 456" if totp.now() != "123456" else "654321").status_code == 401
    # (the code used to confirm is spent: a code from the next 30 seconds)
    later = int(__import__("time").time()) + 30
    monkeypatch.setattr(auth.time, "time", lambda: later)
    code = totp.at(later)
    assert sign_in(anon, code=code).json() == {"signed_in": True}
    assert sign_in(TestClient(app, base_url="https://testserver"), code=code).status_code == 401    # used: not again
    # a recovery code, once
    phone_lost = TestClient(app, base_url="https://testserver")
    assert sign_in(phone_lost, code=recovery[0].lower()).json() == {"signed_in": True}
    assert sign_in(TestClient(app, base_url="https://testserver"), code=recovery[0]).status_code == 401
    assert client.get("/api/auth/recovery-codes").json() == {"unused": 9, "total": 10}
    with db() as conn:              # (this test's own wrong codes count towards the guessing limit: start afresh)
        conn.execute("DELETE FROM auth_failures")
    fresh = client.post("/api/auth/recovery-codes", json={"password": TEST_PASSWORD}).json()["recovery_codes"]
    assert len(set(fresh) - set(recovery)) == 10 and client.get("/api/auth/recovery-codes").json()["unused"] == 10


def test_turning_the_authenticator_off_needs_password_and_code(client, anon, monkeypatch):
    totp, recovery = turn_on_authenticator(client)
    assert client.post("/api/auth/totp/start", json={"password": TEST_PASSWORD}).status_code == 409
    assert client.post("/api/auth/totp/off", json={"password": TEST_PASSWORD, "code": "000000"}).status_code == 401
    assert client.post("/api/auth/totp/off", json={"password": TEST_PASSWORD, "code": recovery[3]}).json() == {"totp_on": False}
    assert sign_in(anon).json() == {"signed_in": True}                          # just the password again


# ---------------------------------------------------------------- devices
def test_signed_in_devices_listed_and_signed_out(client, anon):
    sign_in(anon)
    devices = client.get("/api/auth/sessions").json()
    assert len(devices) == 2 and sum(d["this_device"] for d in devices) == 1
    other = next(d for d in devices if not d["this_device"])
    assert client.delete(f"/api/auth/sessions/{other['session_id']}").status_code == 204
    assert anon.get("/api/supplies").status_code == 401
    sign_in(anon)
    assert client.post("/api/auth/sessions/others/sign-out").json() == {"signed_out": 1}
    assert anon.get("/api/supplies").status_code == 401 and client.get("/api/supplies").status_code == 200
    me = client.get("/api/auth/sessions").json()[0]
    assert client.delete(f"/api/auth/sessions/{me['session_id']}").status_code == 204   # signing this one out
    assert client.get("/api/supplies").status_code == 401
    assert client.delete("/api/auth/sessions/999999").status_code == 401


# ---------------------------------------------------------------- passkeys (a software authenticator)
HOST = "travel.test:8443"
ORIGIN = f"https://{HOST}"


class FakeAuthenticator:
    """Makes and uses a passkey the way a phone does (ES256, no attestation), so the real checks run."""
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(16)
        self.count = 0

    def _auth_data(self, rp_id, flags, attested=b""):
        self.count += 1
        return hashlib.sha256(rp_id.encode()).digest() + bytes([flags]) + self.count.to_bytes(4, "big") + attested

    def create(self, options, origin=ORIGIN):
        nums = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})
        attested = bytes(16) + len(self.credential_id).to_bytes(2, "big") + self.credential_id + cose
        auth_data = self._auth_data(options["rp"]["id"], 0x45, attested)            # user present + verified + key
        client = json.dumps({"type": "webauthn.create", "challenge": options["challenge"], "origin": origin}).encode()
        return {"id": b64(self.credential_id), "rawId": b64(self.credential_id), "type": "public-key",
                "response": {"clientDataJSON": b64(client),
                             "attestationObject": b64(cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data}))}}

    def get(self, options, origin=ORIGIN):
        auth_data = self._auth_data(options["rpId"], 0x05)
        client = json.dumps({"type": "webauthn.get", "challenge": options["challenge"], "origin": origin}).encode()
        signature = self.key.sign(auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64(self.credential_id), "rawId": b64(self.credential_id), "type": "public-key",
                "response": {"clientDataJSON": b64(client), "authenticatorData": b64(auth_data), "signature": b64(signature),
                             "userHandle": b64(b"off-the-clock-1")}}


def named(client_or_token=None):
    c = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})
    if client_or_token:
        c.cookies.set(auth.COOKIE, client_or_token)
    return c


def test_a_passkey_made_then_used_to_sign_in(client):
    from tests.conftest import sign_in_directly
    me = named(sign_in_directly())
    device = FakeAuthenticator()
    options = me.post("/api/auth/passkeys/register/options").json()
    assert options["rp"]["id"] == "travel.test" and options["authenticatorSelection"]["residentKey"] == "required"
    made = me.post("/api/auth/passkeys/register/verify", json={"credential": device.create(options), "name": "My phone"})
    assert made.status_code == 201, made.text
    assert [p["name"] for p in me.get("/api/auth/passkeys").json()] == ["My phone"]
    # sign in with it on a new device (no password)
    stranger = named()
    assert stranger.get("/api/supplies").status_code == 401
    challenge = stranger.post("/api/auth/passkey/login/options").json()
    r = stranger.post("/api/auth/passkey/login/verify", json={"credential": device.get(challenge)})
    assert r.json() == {"signed_in": True}, r.text
    assert stranger.get("/api/supplies").status_code == 200
    assert any(s["method"] == "passkey" for s in me.get("/api/auth/sessions").json())
    # the same answer again (a replay) is refused: its challenge is spent
    assert named().post("/api/auth/passkey/login/verify", json={"credential": device.get(challenge)}).status_code == 422
    # another device's key, a wrong site, a removed passkey: no
    impostor = FakeAuthenticator()
    impostor.credential_id = device.credential_id
    assert named().post("/api/auth/passkey/login/verify",
                        json={"credential": impostor.get(named().post("/api/auth/passkey/login/options").json())}).status_code == 401
    assert named().post("/api/auth/passkey/login/verify",
                        json={"credential": device.get(named().post("/api/auth/passkey/login/options").json(),
                                                       origin="https://evil.example")}).status_code == 401
    pid = me.get("/api/auth/passkeys").json()[0]["passkey_id"]
    assert me.patch(f"/api/auth/passkeys/{pid}", json={"name": "Old phone"}).json()["name"] == "Old phone"
    assert me.delete(f"/api/auth/passkeys/{pid}").status_code == 204
    assert named().post("/api/auth/passkey/login/verify",
                        json={"credential": device.get(named().post("/api/auth/passkey/login/options").json())}).status_code == 401


def test_passkeys_need_the_apps_name_not_an_ip(client):
    by_ip = TestClient(app, base_url="https://10.0.0.33:8443", headers={"Origin": "https://10.0.0.33:8443"})
    by_ip.cookies.set(auth.COOKIE, client.cookies.get(auth.COOKIE))
    r = by_ip.post("/api/auth/passkeys/register/options")
    assert r.status_code == 422 and ".local" in r.json()["detail"]
    assert by_ip.get("/api/auth/status").json()["passkey_name"] is False


def test_a_passkey_answer_for_another_site_is_refused(client):
    from tests.conftest import sign_in_directly
    me = named(sign_in_directly())
    device = FakeAuthenticator()
    options = me.post("/api/auth/passkeys/register/options").json()
    r = me.post("/api/auth/passkeys/register/verify",
                json={"credential": device.create(options, origin="https://phish.example"), "name": "x"})
    assert r.status_code == 422


# ---------------------------------------------------------------- on the PC
def test_setting_the_password_on_the_pc(client, monkeypatch, capsys):
    totp, _ = turn_on_authenticator(client)
    monkeypatch.setattr("sys.stdin", io.StringIO("too short\n"))
    assert auth.main(["set-password", "--stdin"]) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("﻿a long new password for the pc\r\n"))   # (as a PowerShell pipe sends it)
    assert auth.main(["set-password", "--stdin", "--reset-authenticator", "--sign-out-everywhere"]) == 0
    assert "Authenticator turned off" in capsys.readouterr().out
    assert client.get("/api/supplies").status_code == 401                        # everyone signed out
    fresh = TestClient(app, base_url="https://testserver")
    assert sign_in(fresh, "a long new password for the pc").json() == {"signed_in": True}   # no code needed now
