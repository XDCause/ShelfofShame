-- Goals that count themselves, habits, goals inside bigger goals, and steps become to-dos (2026-10-21).
--
--   source        what the goal counts by itself, from a hobby's own records (api/app/goal_sources.py: books
--                 finished, km hiked, kits finished, a chess rating...). NULL = you update the number yourself.
--   kind          'target' (reach a number / finish the to-dos) or 'habit' (so many times a week or month)
--   habit_times   a habit's "how many" each week / month; habit_every: 'week' or 'month'
--   parent_id     a goal this one feeds into (a year's goal under a 3-year goal). The bigger goal going leaves this one.
--
-- Steps and to-dos were two lists of the same thing: each step becomes a to-do under its goal (no day; ticked ones
-- stay done; the order kept by their created time). todos.from_step remembers which step it came from, so running
-- this again copies nothing twice. goal_steps itself is left as it was (nothing reads it now) - a safety net.
-- Idempotent.

ALTER TABLE goals ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'target';
ALTER TABLE goals ADD COLUMN IF NOT EXISTS habit_times INT;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS habit_every TEXT;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS parent_id INT REFERENCES goals ON DELETE SET NULL;

ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_kind_check;
ALTER TABLE goals ADD CONSTRAINT goals_kind_check CHECK (kind IN ('target', 'habit'));
ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_habit_check;
ALTER TABLE goals ADD CONSTRAINT goals_habit_check
    CHECK (habit_every IS NULL OR habit_every IN ('week', 'month'));
ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_habit_times_check;
ALTER TABLE goals ADD CONSTRAINT goals_habit_times_check CHECK (habit_times IS NULL OR habit_times BETWEEN 1 AND 1000);
ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_parent_check;
ALTER TABLE goals ADD CONSTRAINT goals_parent_check CHECK (parent_id IS NULL OR parent_id <> goal_id);
CREATE INDEX IF NOT EXISTS goals_parent_idx ON goals (parent_id);

ALTER TABLE todos ADD COLUMN IF NOT EXISTS from_step INT UNIQUE;
CREATE INDEX IF NOT EXISTS todos_goal_idx ON todos (goal_id);

INSERT INTO todos (title, goal_id, hobby, done_at, created_at, from_step)
SELECT left(btrim(s.text), 200), s.goal_id, g.hobby,                  -- (a to-do's words: 200 at most)
       CASE WHEN s.done THEN COALESCE(s.done_on::timestamptz + interval '12 hours', now()) END,
       g.created_at + s.sort_order * interval '1 second' + s.step_id * interval '1 millisecond',
       s.step_id
FROM goal_steps s JOIN goals g USING (goal_id)
WHERE NOT EXISTS (SELECT 1 FROM todos t WHERE t.from_step = s.step_id);
