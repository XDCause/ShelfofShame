-- Core + travel extras (2026-11-16). Idempotent: safe to run again.
--   focus_sessions   a timed stretch of focus on a to-do or a goal (api/app/focus.py). The start time lives here, so a
--                    reload (or another device) still sees the timer running. paused_seconds = time spent paused.
--   habit_freezes    a day you froze on a habit goal: the week / month it falls in doesn't break the streak (goals_review.py)
--   trip_people      who is on a trip, for splitting costs (travel_extras.py)
--   paid_by + *_shares   who paid an expense or booking, and who shares it (none shared = everyone on the trip)

CREATE TABLE IF NOT EXISTS focus_sessions (
    session_id     serial PRIMARY KEY,
    todo_id        integer REFERENCES todos (todo_id) ON DELETE SET NULL,
    goal_id        integer REFERENCES goals (goal_id) ON DELETE SET NULL,
    label          text,
    minutes        integer NOT NULL DEFAULT 25 CHECK (minutes BETWEEN 1 AND 480),
    started_at     timestamptz NOT NULL DEFAULT now(),
    paused_at      timestamptz,
    paused_seconds integer NOT NULL DEFAULT 0 CHECK (paused_seconds >= 0),
    ended_at       timestamptz,
    focused_seconds integer CHECK (focused_seconds >= 0),
    status         text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'paused', 'done', 'stopped'))
);
CREATE INDEX IF NOT EXISTS focus_sessions_todo_idx ON focus_sessions (todo_id);
CREATE INDEX IF NOT EXISTS focus_sessions_goal_idx ON focus_sessions (goal_id);
CREATE INDEX IF NOT EXISTS focus_sessions_started_idx ON focus_sessions (started_at);

CREATE TABLE IF NOT EXISTS habit_freezes (
    freeze_id  serial PRIMARY KEY,
    goal_id    integer NOT NULL REFERENCES goals (goal_id) ON DELETE CASCADE,
    day        date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (goal_id, day)
);

CREATE TABLE IF NOT EXISTS trip_people (
    person_id  serial PRIMARY KEY,
    trip_id    integer NOT NULL REFERENCES trips ON DELETE CASCADE,
    name       text NOT NULL CHECK (btrim(name) <> '' AND length(name) <= 60),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS trip_people_name_idx ON trip_people (trip_id, lower(name));

ALTER TABLE trip_expenses ADD COLUMN IF NOT EXISTS paid_by integer REFERENCES trip_people (person_id) ON DELETE SET NULL;
ALTER TABLE trip_bookings ADD COLUMN IF NOT EXISTS paid_by integer REFERENCES trip_people (person_id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS trip_expense_shares (
    expense_id integer NOT NULL REFERENCES trip_expenses ON DELETE CASCADE,
    person_id  integer NOT NULL REFERENCES trip_people ON DELETE CASCADE,
    PRIMARY KEY (expense_id, person_id)
);
CREATE TABLE IF NOT EXISTS trip_booking_shares (
    booking_id integer NOT NULL REFERENCES trip_bookings ON DELETE CASCADE,
    person_id  integer NOT NULL REFERENCES trip_people ON DELETE CASCADE,
    PRIMARY KEY (booking_id, person_id)
);
