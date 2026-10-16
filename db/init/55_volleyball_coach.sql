-- Volleyball Coach: your own coaching notes.
--   kind      drill (how to practise something), fix (an issue you're having, with tips), position (a role)
--   skill     Serving, Passing, Setting, Attacking, Blocking, Defence, Footwork... (free text, suggested)
--   position  Setter, Outside, Opposite, Middle, Libero, Defensive specialist (free text, suggested)
--   status    for fixes: 'working on' or 'sorted' (NULL for drills and positions)
--   links     web addresses (YouTube shows a picture); video_ids = your own uploaded videos
-- Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS volleyball_coach (
    note_id     SERIAL PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('drill', 'fix', 'position')),
    title       TEXT NOT NULL CHECK (btrim(title) <> ''),
    skill       TEXT,
    position    TEXT,
    body        TEXT,
    status      TEXT CHECK (status IN ('working on', 'sorted')),
    links       TEXT[] NOT NULL DEFAULT '{}',
    video_ids   INT[] NOT NULL DEFAULT '{}',
    pinned      BOOLEAN NOT NULL DEFAULT false,
    starter     BOOLEAN NOT NULL DEFAULT false,     -- came from the starter set (not your own)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((kind = 'fix') = (status IS NOT NULL))
);

DROP TRIGGER IF EXISTS volleyball_coach_set_updated_at ON volleyball_coach;
CREATE TRIGGER volleyball_coach_set_updated_at
    BEFORE UPDATE ON volleyball_coach
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
