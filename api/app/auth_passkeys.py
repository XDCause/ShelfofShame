"""Signing in with a passkey (WebAuthn: Face ID, a fingerprint, a PIN): adding, naming and removing them, and signing
in with one. Split out of auth.py (2026-10-22); like auth.py, each route checks what it needs itself (no blanket
session check)."""
import json
import secrets
import time
from urllib.parse import urlsplit

import webauthn
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from .db import db, found
from .auth import (CHALLENGES, CHALLENGE_SECONDS, RP_NAME, check_origin, client_address, failed,
                   passkey_host, require_session, start_session, too_many_failures)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
