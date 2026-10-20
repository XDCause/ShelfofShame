-- To-do list (2026-10-20, user: "change [Home's goals] to a to-do list, and build that out under the goals as a new tab").
-- Things to do soon - the day-to-day under the big (three-year) goals: a due day if it has one, high priority or not,
-- a hobby, a goal it moves forward, and repeating ones (done -> the next one appears). api/app/todos.py. Idempotent.
CREATE TABLE IF NOT EXISTS todos (
    todo_id     serial PRIMARY KEY,
    title       text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    notes       text CHECK (length(notes) <= 2000),
    due_on      date,
    priority    text NOT NULL DEFAULT 'normal' CHECK (priority IN ('normal', 'high')),
    hobby       text,                         -- a module's id (checked by the API), or none
    goal_id     integer REFERENCES goals (goal_id) ON DELETE SET NULL,
    repeats     text NOT NULL DEFAULT 'never' CHECK (repeats IN ('never', 'daily', 'weekly', 'monthly')),
    done_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS todos_open ON todos (due_on) WHERE done_at IS NULL;
