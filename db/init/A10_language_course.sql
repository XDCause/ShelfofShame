-- Language learning's built-in courses (2026-11-17): the app teaches a language, lesson by lesson (Language learning >
-- Learn; api/app/language_course.py). The course content is JSON in the API (api/app/data/courses/<code>/uNN.json);
-- the database keeps only what you've done. Idempotent.
--   lang_languages.course   the course a language follows ('es' = Spanish), NULL = none. A language named Spanish /
--                           Español gets 'es' by itself (the API on adding one; here, the ones already there)
--   lang_lesson_runs        each time a lesson was finished: when, score %, mistakes, seconds (they count as study
--                           minutes: language.MINUTES), the lesson's title and unit as they were then, cards it added
--   lang_cards.lesson_id    the lesson that put a card in the deck (NULL = one you added yourself)
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'lang_languages' AND column_name = 'course') THEN
        ALTER TABLE lang_languages ADD COLUMN course text;
        -- (only when the column is new: a course switched off later stays off)
        UPDATE lang_languages SET course = 'es' WHERE lower(btrim(name)) IN ('spanish', 'español', 'espanol', 'castellano');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'lang_languages_course_code') THEN
        ALTER TABLE lang_languages ADD CONSTRAINT lang_languages_course_code CHECK (course ~ '^[a-z]{2,3}$');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS lang_lesson_runs (
    run_id       serial PRIMARY KEY,
    language_id  integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    lesson_id    text NOT NULL,
    unit         smallint NOT NULL,
    title        text NOT NULL,
    done_at      timestamptz NOT NULL DEFAULT now(),
    score        smallint NOT NULL,
    mistakes     smallint NOT NULL DEFAULT 0,
    seconds      integer NOT NULL DEFAULT 0,
    cards_added  smallint NOT NULL DEFAULT 0,
    CONSTRAINT lang_lesson_runs_lesson_form CHECK (lesson_id ~ '^[a-z]{2,3}-u[0-9]{2}-l[0-9]{1,2}$'),
    CONSTRAINT lang_lesson_runs_unit_range CHECK (unit BETWEEN 1 AND 99),
    CONSTRAINT lang_lesson_runs_score_range CHECK (score BETWEEN 0 AND 100),
    CONSTRAINT lang_lesson_runs_mistakes_range CHECK (mistakes BETWEEN 0 AND 1000),
    CONSTRAINT lang_lesson_runs_seconds_range CHECK (seconds BETWEEN 0 AND 14400),
    CONSTRAINT lang_lesson_runs_cards_range CHECK (cards_added >= 0)
);
CREATE INDEX IF NOT EXISTS lang_lesson_runs_language_idx ON lang_lesson_runs (language_id, lesson_id);
CREATE INDEX IF NOT EXISTS lang_lesson_runs_at_idx ON lang_lesson_runs (done_at);

ALTER TABLE lang_cards ADD COLUMN IF NOT EXISTS lesson_id text;
CREATE INDEX IF NOT EXISTS lang_cards_lesson_idx ON lang_cards (language_id, lesson_id) WHERE lesson_id IS NOT NULL;

COMMIT;
