-- Signing in (2026-10-20, user: "build a secure login"). One account (yours): a password (Argon2 hash), an optional
-- authenticator app (TOTP) with one-time recovery codes, passkeys, and a 30-day session per signed-in device.
-- There's no sign-up page: the password is set on the PC itself (set-password.ps1). api/app/auth.py. Idempotent.
CREATE TABLE IF NOT EXISTS auth_account (
    account_id      smallint PRIMARY KEY DEFAULT 1 CHECK (account_id = 1),     -- only ever one
    password_hash   text NOT NULL,
    totp_secret     text,                     -- set while being set up; used once totp_on
    totp_on         boolean NOT NULL DEFAULT false,
    totp_last_step  bigint,                   -- the last 30-second step a code was used for (no replays)
    changed_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_recovery_codes (
    code_hash  text PRIMARY KEY,              -- sha256 of the code; each works once
    used_at    timestamptz
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id    serial PRIMARY KEY,
    token_hash    text NOT NULL UNIQUE,       -- sha256 of the cookie's random token (the token itself is never stored)
    method        text NOT NULL CHECK (method IN ('password', 'passkey')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    user_agent    text,
    ip            text
);
CREATE INDEX IF NOT EXISTS auth_sessions_expires ON auth_sessions (expires_at);

CREATE TABLE IF NOT EXISTS auth_passkeys (
    passkey_id     serial PRIMARY KEY,
    credential_id  bytea NOT NULL UNIQUE,
    public_key     bytea NOT NULL,
    sign_count     bigint NOT NULL DEFAULT 0,
    name           text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    rp_id          text NOT NULL,             -- the address it was made on (a passkey only works there)
    created_at     timestamptz NOT NULL DEFAULT now(),
    last_used_at   timestamptz
);

-- Wrong passwords / codes, for slowing down guessing (kept a day).
CREATE TABLE IF NOT EXISTS auth_failures (
    at  timestamptz NOT NULL DEFAULT now(),
    ip  text
);
CREATE INDEX IF NOT EXISTS auth_failures_at ON auth_failures (at);
