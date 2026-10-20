"""Signing in: one account (yours), a password and an authenticator app, or a passkey; a 30-day session per device.

How it's kept safe:
  - There's no sign-up page. The password is set (or reset, if you lose it or your authenticator) on the PC itself:
    .\\set-password.ps1, which runs `python -m app.auth set-password` inside this container.
  - The password is kept only as an Argon2id hash (argon2-cffi). Too many wrong passwords or codes from one address
    in 15 minutes (or from everywhere at once) and signing in waits.
  - An authenticator app (TOTP, pyotp): a 6-digit code after the password; each code works once. Ten one-time
    recovery codes, shown once, for a lost phone. A passkey (py_webauthn) signs in on its own: it's already two things
    (the device, and your face / fingerprint / PIN) and can't be phished.
  - The session is a random token in a cookie the page's scripts can't read (HttpOnly), sent only over HTTPS (Secure)
    and never by another site (SameSite=Strict); only its sha256 is stored. Anything that changes data must also come
    from the app's own address (the Origin check), against cross-site request forgery.
  - Every API route needs a session (main.py adds require_session to every router) except signing in itself and
    /api/health. tests/test_auth.py checks each route refuses a stranger.
"""
import argparse
import getpass
import hashlib
import ipaddress
import json
import secrets
import sys
import time
from datetime import timedelta
from urllib.parse import urlsplit

import pyotp
import segno
import webauthn
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from .db import db, found

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE = "otc_session"
SESSION_DAYS = 30
MIN_PASSWORD = 12
HASHER = PasswordHasher()                   # Argon2id with the library's (RFC 9106) defaults
FAIL_WINDOW = timedelta(minutes=15)
FAILS_PER_ADDRESS = 5                       # wrong passwords / codes from one address in FAIL_WINDOW
FAILS_EVERYWHERE = 20                       # ...or from all addresses together (slow, spread-out guessing)
RECOVERY_CODES = 10
CHALLENGE_SECONDS = 300
RP_NAME = "Off the Clock"
# Passkey challenges waiting for an answer (one API worker, so memory is fine): challenge -> (purpose, expires)
CHALLENGES: dict[str, tuple[str, float]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def client_address(request: Request) -> str:
    # nginx sets X-Real-IP; the API's own port is only open to this PC, so nobody else can send it directly.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


def account(conn) -> dict | None:
    return conn.execute("SELECT * FROM auth_account WHERE account_id = 1").fetchone()


def check_origin(request: Request):
    """A change must come from a page of this app: a browser always says where a request comes from (Origin) on
    POST / PUT / PATCH / DELETE, and another site's page can't pretend. (No Origin: not a browser - curl, tests.)"""
    origin = request.headers.get("origin")
    if origin is None:
        return
    host = urlsplit("//" + request.headers.get("host", "")).hostname
    if urlsplit(origin).hostname != host:
        raise HTTPException(403, "That request came from another site, so it was refused.")


def too_many_failures(conn, address: str):
    rows = conn.execute("""SELECT count(*) FILTER (WHERE ip = %s)::int AS here, count(*)::int AS everywhere
                           FROM auth_failures WHERE at > now() - %s""", (address, FAIL_WINDOW)).fetchone()
    if rows["here"] >= FAILS_PER_ADDRESS or rows["everywhere"] >= FAILS_EVERYWHERE:
        raise HTTPException(429, "Too many wrong tries. Wait 15 minutes, then try again.")


def failed(address: str, message: str):
    """Note a wrong password / code (in its own transaction, so it sticks) and refuse."""
    with db() as conn:
        conn.execute("INSERT INTO auth_failures (ip) VALUES (%s)", (address,))
        conn.execute("DELETE FROM auth_failures WHERE at < now() - interval '1 day'")
    raise HTTPException(401, message)


def password_ok(conn, password: str) -> bool:
    acct = account(conn)
    if not acct:
        return False
    try:
        HASHER.verify(acct["password_hash"], password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    if HASHER.check_needs_rehash(acct["password_hash"]):
        conn.execute("UPDATE auth_account SET password_hash = %s", (HASHER.hash(password),))
    return True


def code_ok(conn, code: str) -> bool:
    """A 6-digit code from the authenticator (each 30-second code once only), or an unused recovery code."""
    acct = account(conn)
    code = (code or "").strip().replace(" ", "")
    if acct and acct["totp_secret"] and code.isdigit() and len(code) == 6:
        totp = pyotp.TOTP(acct["totp_secret"])
        now = int(time.time())
        for drift in (0, -30, 30):                                  # a phone clock a little out is fine
            step = (now + drift) // 30
            if secrets.compare_digest(totp.at(now + drift), code) and step > (acct["totp_last_step"] or 0):
                conn.execute("UPDATE auth_account SET totp_last_step = %s", (step,))
                return True
        return False
    used = conn.execute("UPDATE auth_recovery_codes SET used_at = now() WHERE code_hash = %s AND used_at IS NULL "
                        "RETURNING code_hash", (sha256(code.upper()),)).fetchone()
    return bool(used)


def start_session(conn, request: Request, response: Response, method: str):
    token = secrets.token_urlsafe(32)
    conn.execute("""INSERT INTO auth_sessions (token_hash, method, expires_at, user_agent, ip)
                    VALUES (%s, %s, now() + %s, %s, %s)""",
                 (sha256(token), method, timedelta(days=SESSION_DAYS), (request.headers.get("user-agent") or "")[:300],
                  client_address(request)))
    conn.execute("DELETE FROM auth_sessions WHERE expires_at < now()")
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, secure=True, samesite="strict", path="/")


def session_of(conn, request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = conn.execute("SELECT session_id, method, last_seen_at < now() - interval '5 minutes' AS stale "
                       "FROM auth_sessions WHERE token_hash = %s AND expires_at > now()", (sha256(token),)).fetchone()
    if row and row["stale"]:
        conn.execute("UPDATE auth_sessions SET last_seen_at = now(), ip = %s WHERE session_id = %s",
                     (client_address(request), row["session_id"]))
    return row


def require_session(request: Request):
    """Every router but this one depends on this (main.py): a signed-in device, and changes from this app only."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
    with db() as conn:
        if not session_of(conn, request):
            raise HTTPException(401, "Sign in first.")


def new_recovery_codes(conn) -> list[str]:
    conn.execute("DELETE FROM auth_recovery_codes")
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper() for _ in range(RECOVERY_CODES)]
    for c in codes:
        conn.execute("INSERT INTO auth_recovery_codes (code_hash) VALUES (%s)", (sha256(c),))
    return codes


# ---------------------------------------------------------------------------
# Status, signing in and out
# ---------------------------------------------------------------------------
@router.get("/status")
def status(request: Request):
    with db() as conn:
        acct = account(conn)
        signed_in = bool(session_of(conn, request))
        passkeys = conn.execute("SELECT count(*)::int AS n FROM auth_passkeys").fetchone()["n"]
    return {"set_up": bool(acct), "signed_in": signed_in, "totp_on": bool(acct and acct["totp_on"]),
            "passkeys": passkeys if signed_in else None, "passkey_name": passkey_host(request) is not None}


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    code: str | None = Field(None, max_length=20)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    """The password, then (with an authenticator) its code: without one it answers {"need_code": true}."""
    check_origin(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        if not account(conn):
            raise HTTPException(409, "There's no password yet. On the PC, run .\\set-password.ps1 in the app's folder.")
        if not password_ok(conn, body.password):
            conn.rollback()
            failed(address, "That password isn't right.")
        if account(conn)["totp_on"]:
            if not body.code:
                return {"need_code": True}
            if not code_ok(conn, body.code):
                conn.rollback()
                failed(address, "That code isn't right (or it's been used).")
        start_session(conn, request, response, "password")
    return {"signed_in": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    check_origin(request)
    token = request.cookies.get(COOKIE)
    if token:
        with db() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (sha256(token),))
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return {"signed_in": False}


# ---------------------------------------------------------------------------
# Signed-in devices
# ---------------------------------------------------------------------------
@router.get("/sessions")
def sessions(request: Request):
    require_session(request)
    mine = sha256(request.cookies.get(COOKIE, ""))
    with db() as conn:
        return conn.execute("""SELECT session_id, method, created_at, last_seen_at, expires_at, user_agent, ip,
                                      token_hash = %s AS this_device
                               FROM auth_sessions WHERE expires_at > now() ORDER BY last_seen_at DESC""", (mine,)).fetchall()


@router.delete("/sessions/{session_id}")
def sign_out_device(session_id: int, request: Request, response: Response):
    require_session(request)
    with db() as conn:
        row = found(conn.execute("DELETE FROM auth_sessions WHERE session_id = %s RETURNING token_hash", (session_id,)).fetchone(),
                    "Device")
    if row["token_hash"] == sha256(request.cookies.get(COOKIE, "")):
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return Response(status_code=204, headers=dict(response.headers))


@router.post("/sessions/others/sign-out")
def sign_out_others(request: Request):
    require_session(request)
    with db() as conn:
        n = conn.execute("DELETE FROM auth_sessions WHERE token_hash <> %s", (sha256(request.cookies.get(COOKIE, "")),)).rowcount
    return {"signed_out": n}


# ---------------------------------------------------------------------------
# Password and authenticator
# ---------------------------------------------------------------------------
class PasswordIn(BaseModel):
    current: str = Field(min_length=1, max_length=200)
    new: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/password")
def change_password(body: PasswordIn, request: Request):
    """A new password (needs the current one); every other device is signed out."""
    require_session(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        if not password_ok(conn, body.current):
            conn.rollback()
            failed(address, "Your current password isn't right.")
        if body.new == body.current:
            raise HTTPException(422, "That's the password you have now.")
        conn.execute("UPDATE auth_account SET password_hash = %s, changed_at = now()", (HASHER.hash(body.new),))
        conn.execute("DELETE FROM auth_sessions WHERE token_hash <> %s", (sha256(request.cookies.get(COOKIE, "")),))
    return {"changed": True}


class ConfirmIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/totp/start")
def totp_start(body: ConfirmIn, request: Request):
    """A new secret for an authenticator app (not on until a code from it is confirmed): its QR code and the text."""
    require_session(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        if not password_ok(conn, body.password):
            conn.rollback()
            failed(address, "That password isn't right.")
        if account(conn)["totp_on"]:
            raise HTTPException(409, "An authenticator is already set up. Turn it off first to use a new one.")
        secret = pyotp.random_base32()
        conn.execute("UPDATE auth_account SET totp_secret = %s", (secret,))
    uri = pyotp.TOTP(secret).provisioning_uri(name="you", issuer_name=RP_NAME)
    return {"secret": secret, "uri": uri, "qr_svg": segno.make(uri, error="m").svg_inline(scale=5, dark="#17211b", light="#ffffff")}


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=20)


@router.post("/totp/confirm")
def totp_confirm(body: CodeIn, request: Request):
    """The first code from the app turns it on; the recovery codes come back once (keep them somewhere safe)."""
    require_session(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        acct = account(conn)
        if acct["totp_on"] or not acct["totp_secret"]:
            raise HTTPException(409, "Start setting up the authenticator first.")
        if not code_ok(conn, body.code):
            conn.rollback()
            failed(address, "That code isn't right - check the time on your phone, then try the next one.")
        conn.execute("UPDATE auth_account SET totp_on = true")
        return {"totp_on": True, "recovery_codes": new_recovery_codes(conn)}


class OffIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=6, max_length=20)


@router.post("/totp/off")
def totp_off(body: OffIn, request: Request):
    require_session(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        if not (password_ok(conn, body.password) and code_ok(conn, body.code)):
            conn.rollback()
            failed(address, "The password or the code isn't right.")
        conn.execute("UPDATE auth_account SET totp_on = false, totp_secret = NULL, totp_last_step = NULL")
        conn.execute("DELETE FROM auth_recovery_codes")
    return {"totp_on": False}


@router.post("/recovery-codes")
def recovery_codes(body: ConfirmIn, request: Request):
    """Ten new recovery codes (the old ones stop working)."""
    require_session(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
        if not password_ok(conn, body.password):
            conn.rollback()
            failed(address, "That password isn't right.")
        if not account(conn)["totp_on"]:
            raise HTTPException(409, "Recovery codes go with an authenticator: set one up first.")
        return {"recovery_codes": new_recovery_codes(conn)}


@router.get("/recovery-codes")
def recovery_codes_left(request: Request):
    require_session(request)
    with db() as conn:
        return conn.execute("SELECT count(*) FILTER (WHERE used_at IS NULL)::int AS unused, count(*)::int AS total "
                            "FROM auth_recovery_codes").fetchone()


# ---------------------------------------------------------------------------
# Passkeys (WebAuthn)
# ---------------------------------------------------------------------------
def passkey_host(request: Request) -> str | None:
    """The address passkeys belong to: the app's name (travel-laptop.local), never a bare IP (WebAuthn won't)."""
    host = urlsplit("//" + request.headers.get("host", "")).hostname or ""
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        return host or None


def _origin(request: Request, rp_id: str) -> str:
    origin = request.headers.get("origin") or ""
    parts = urlsplit(origin)
    if parts.scheme != "https" or parts.hostname != rp_id:
        raise HTTPException(422, "Passkeys work only over https at the app's name.")
    return origin


def _challenge(purpose: str) -> bytes:
    now = time.time()
    for key, (_, expires) in list(CHALLENGES.items()):
        if expires < now:
            CHALLENGES.pop(key, None)
    challenge = secrets.token_bytes(32)
    CHALLENGES[bytes_to_base64url(challenge)] = (purpose, now + CHALLENGE_SECONDS)
    return challenge


def _take_challenge(credential: dict, purpose: str) -> bytes:
    """The challenge the browser signed (from its clientDataJSON), if it's one we gave out, unused and fresh."""
    try:
        client = json.loads(base64url_to_bytes(credential["response"]["clientDataJSON"]))
        challenge = client["challenge"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "That passkey answer couldn't be read.") from None
    given = CHALLENGES.pop(challenge, None)
    if not given or given[0] != purpose or given[1] < time.time():
        raise HTTPException(422, "That passkey request has expired. Try again.")
    return base64url_to_bytes(challenge)


def _no_ip(request: Request) -> str:
    rp_id = passkey_host(request)
    if not rp_id:
        raise HTTPException(422, "Passkeys need the app's name, not an IP address: open it at https://<this PC's name>.local:8443.")
    return rp_id


@router.post("/passkeys/register/options")
def passkey_register_options(request: Request):
    require_session(request)
    rp_id = _no_ip(request)
    with db() as conn:
        have = conn.execute("SELECT credential_id FROM auth_passkeys").fetchall()
    options = webauthn.generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_id=b"off-the-clock-1", user_name="you", user_display_name="You",
        challenge=_challenge("register"),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=bytes(r["credential_id"])) for r in have],
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED,
                                                               user_verification=UserVerificationRequirement.REQUIRED))
    return json.loads(options_to_json(options))


class PasskeyIn(BaseModel):
    credential: dict
    name: str = Field("Passkey", min_length=1, max_length=60)


@router.post("/passkeys/register/verify", status_code=201)
def passkey_register_verify(body: PasskeyIn, request: Request):
    require_session(request)
    rp_id = _no_ip(request)
    challenge = _take_challenge(body.credential, "register")
    try:
        done = webauthn.verify_registration_response(credential=body.credential, expected_challenge=challenge,
                                                     expected_rp_id=rp_id, expected_origin=_origin(request, rp_id),
                                                     require_user_verification=True)
    except Exception as e:      # py_webauthn raises several kinds; all mean "not a valid passkey answer"
        raise HTTPException(422, f"The passkey wasn't accepted ({e}).") from None
    with db() as conn:
        return conn.execute("""INSERT INTO auth_passkeys (credential_id, public_key, sign_count, name, rp_id)
                               VALUES (%s, %s, %s, %s, %s) RETURNING passkey_id, name, rp_id, created_at, last_used_at""",
                            (done.credential_id, done.credential_public_key, done.sign_count, body.name.strip(), rp_id)).fetchone()


@router.get("/passkeys")
def passkeys(request: Request):
    require_session(request)
    with db() as conn:
        return conn.execute("SELECT passkey_id, name, rp_id, created_at, last_used_at FROM auth_passkeys ORDER BY created_at").fetchall()


class PasskeyName(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.patch("/passkeys/{passkey_id}")
def rename_passkey(passkey_id: int, body: PasskeyName, request: Request):
    require_session(request)
    with db() as conn:
        return found(conn.execute("UPDATE auth_passkeys SET name = %s WHERE passkey_id = %s "
                                  "RETURNING passkey_id, name, rp_id, created_at, last_used_at",
                                  (body.name.strip(), passkey_id)).fetchone(), "Passkey")


@router.delete("/passkeys/{passkey_id}", status_code=204)
def delete_passkey(passkey_id: int, request: Request):
    require_session(request)
    with db() as conn:
        found(conn.execute("DELETE FROM auth_passkeys WHERE passkey_id = %s RETURNING passkey_id", (passkey_id,)).fetchone(), "Passkey")
    return Response(status_code=204)


@router.post("/passkey/login/options")
def passkey_login_options(request: Request):
    """Sign in with a passkey (no password): the browser asks the device for any passkey it has for this app."""
    check_origin(request)
    rp_id = _no_ip(request)
    with db() as conn:
        too_many_failures(conn, client_address(request))
    options = webauthn.generate_authentication_options(rp_id=rp_id, challenge=_challenge("login"),
                                                       user_verification=UserVerificationRequirement.REQUIRED)
    return json.loads(options_to_json(options))


class AssertionIn(BaseModel):
    credential: dict


@router.post("/passkey/login/verify")
def passkey_login_verify(body: AssertionIn, request: Request, response: Response):
    check_origin(request)
    rp_id = _no_ip(request)
    address = client_address(request)
    with db() as conn:
        too_many_failures(conn, address)
    challenge = _take_challenge(body.credential, "login")
    try:
        raw_id = base64url_to_bytes(body.credential.get("rawId") or body.credential.get("id") or "")
    except (TypeError, ValueError):
        raw_id = b""
    with db() as conn:
        key = conn.execute("SELECT * FROM auth_passkeys WHERE credential_id = %s AND rp_id = %s", (raw_id, rp_id)).fetchone()
        if not key:
            failed(address, "That passkey isn't one this app knows (it may have been removed).")
        try:
            done = webauthn.verify_authentication_response(
                credential=body.credential, expected_challenge=challenge, expected_rp_id=rp_id,
                expected_origin=_origin(request, rp_id), credential_public_key=bytes(key["public_key"]),
                credential_current_sign_count=key["sign_count"], require_user_verification=True)
        except Exception:      # any failed check: not signed in
            failed(address, "That passkey didn't check out.")
        conn.execute("UPDATE auth_passkeys SET sign_count = %s, last_used_at = now() WHERE passkey_id = %s",
                     (done.new_sign_count, key["passkey_id"]))
        start_session(conn, request, response, "passkey")
    return {"signed_in": True}


# ---------------------------------------------------------------------------
# On the PC: set or reset the password (set-password.ps1)
# ---------------------------------------------------------------------------
def set_password(password: str, reset_authenticator: bool = False, sign_out_everywhere: bool = False):
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Use at least {MIN_PASSWORD} characters (a few words together is easy to remember).")
    with db() as conn:
        conn.execute("""INSERT INTO auth_account (account_id, password_hash) VALUES (1, %s)
                        ON CONFLICT (account_id) DO UPDATE SET password_hash = EXCLUDED.password_hash, changed_at = now()""",
                     (HASHER.hash(password),))
        if reset_authenticator:
            conn.execute("UPDATE auth_account SET totp_on = false, totp_secret = NULL, totp_last_step = NULL")
            conn.execute("DELETE FROM auth_recovery_codes")
        if sign_out_everywhere:
            conn.execute("DELETE FROM auth_sessions")
        conn.execute("DELETE FROM auth_failures")          # a fresh start after a reset


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.auth", description="Set or reset the app's password.")
    parser.add_argument("command", choices=["set-password"])
    parser.add_argument("--stdin", action="store_true", help="read the password from standard input (scripts)")
    parser.add_argument("--reset-authenticator", action="store_true", help="turn off the authenticator app (lost phone)")
    parser.add_argument("--sign-out-everywhere", action="store_true", help="sign out every device")
    args = parser.parse_args(argv)
    if args.stdin:
        # (a PowerShell pipe sends a byte-order mark first and \r\n last: neither is part of the password)
        password = sys.stdin.readline().lstrip("﻿").rstrip("\r\n")
    else:
        password = getpass.getpass("New password: ")
        if getpass.getpass("Again: ") != password:
            print("Those didn't match - nothing changed.")
            return 1
    try:
        set_password(password, args.reset_authenticator, args.sign_out_everywhere)
    except ValueError as e:
        print(e)
        return 1
    print("Password set." + (" Authenticator turned off." if args.reset_authenticator else "")
          + (" Every device signed out." if args.sign_out_everywhere else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
