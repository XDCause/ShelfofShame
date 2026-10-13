-- Kit stash, time tracking and build log (2026-10-13).
--
--   models          more statuses (Wanted -> In stash -> In progress / On hold -> Finished -> Gone),
--                   what you paid, when and where, and when you started / finished it
--   model_sessions  time spent: one row per session (ended_at NULL = the timer is running)
--   model_log       dated build notes, each with an optional photo
--   product_info    kit_paints: the "Tamiya Colors required" list from a kit's page (JSON)
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\13_kit_stash.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

-- Statuses: 'Not started' becomes 'In stash' (bought, not begun).
ALTER TABLE models DROP CONSTRAINT IF EXISTS models_status_check;
UPDATE models SET status = 'In stash' WHERE status = 'Not started';
ALTER TABLE models ALTER COLUMN status SET DEFAULT 'In stash';
ALTER TABLE models ADD CONSTRAINT models_status_check
    CHECK (status IN ('Wanted', 'In stash', 'In progress', 'On hold', 'Finished', 'Gone'));

ALTER TABLE models ADD COLUMN IF NOT EXISTS price_paid     NUMERIC(10, 2) CHECK (price_paid >= 0);
ALTER TABLE models ADD COLUMN IF NOT EXISTS purchase_date  DATE;
ALTER TABLE models ADD COLUMN IF NOT EXISTS purchased_from TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS started_on     DATE;
ALTER TABLE models ADD COLUMN IF NOT EXISTS finished_on    DATE;

CREATE TABLE IF NOT EXISTS model_sessions (
    session_id SERIAL PRIMARY KEY,
    model_id   INT NOT NULL REFERENCES models (model_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at   TIMESTAMPTZ,                         -- NULL while the timer is running
    note       TEXT,
    CONSTRAINT model_sessions_order_check CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS model_sessions_model_idx ON model_sessions (model_id, started_at DESC);
-- At most one running timer per model.
CREATE UNIQUE INDEX IF NOT EXISTS model_sessions_running_uq ON model_sessions (model_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS model_log (
    entry_id   SERIAL PRIMARY KEY,
    model_id   INT NOT NULL REFERENCES models (model_id) ON DELETE CASCADE,
    entry_date DATE NOT NULL DEFAULT current_date,
    text       TEXT,
    photo      BYTEA,
    photo_type TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_log_model_idx ON model_log (model_id, entry_date DESC, entry_id DESC);

ALTER TABLE product_info ADD COLUMN IF NOT EXISTS kit_paints JSONB;  -- NULL = not read yet

COMMIT;
