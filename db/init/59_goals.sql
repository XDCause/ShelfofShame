-- Goals (core, beside Home and the Journal): things you're aiming for, written down in detail.
--   goals         title, the hobby it's for (NULL = life in general), why it matters, the details (long
--                 text), status active / paused / done / dropped, a target day, and an optional number
--                 to track (start -> target, the latest value, its unit: "books", "kg", "%"...)
--   goal_steps    the steps to get there, ticked off one by one (done_on = the day you ticked it)
--   goal_updates  a dated progress note; one with a value moves the goal's current value
-- Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS goals (
    goal_id        SERIAL PRIMARY KEY,
    title          TEXT NOT NULL CHECK (btrim(title) <> ''),
    hobby          TEXT,
    why            TEXT,
    details        TEXT,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'done', 'dropped')),
    target_date    DATE,
    unit           TEXT,
    start_value    NUMERIC(14,2),
    target_value   NUMERIC(14,2),
    current_value  NUMERIC(14,2),
    pinned         BOOLEAN NOT NULL DEFAULT false,
    started_on     DATE NOT NULL DEFAULT current_date,
    done_on        DATE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS goals_set_updated_at ON goals;
CREATE TRIGGER goals_set_updated_at
    BEFORE UPDATE ON goals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS goal_steps (
    step_id     SERIAL PRIMARY KEY,
    goal_id     INT NOT NULL REFERENCES goals ON DELETE CASCADE,
    text        TEXT NOT NULL CHECK (btrim(text) <> ''),
    done        BOOLEAN NOT NULL DEFAULT false,
    done_on     DATE,
    sort_order  INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS goal_steps_goal_idx ON goal_steps (goal_id);

CREATE TABLE IF NOT EXISTS goal_updates (
    update_id   SERIAL PRIMARY KEY,
    goal_id     INT NOT NULL REFERENCES goals ON DELETE CASCADE,
    day         DATE NOT NULL DEFAULT current_date,
    text        TEXT,
    value       NUMERIC(14,2),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(coalesce(text, '')) <> '' OR value IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS goal_updates_goal_idx ON goal_updates (goal_id);
