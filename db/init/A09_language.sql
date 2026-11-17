-- Language learning (2026-11-17), a hobby module (api/app/language.py, language_cards.py, srs.py;
-- web/src/modules/language). Idempotent.
--   lang_languages  a language you're learning: its level (CEFR, your own rating), the level you're aiming for and by
--                   when, minutes a day, new cards a day, its voice (a BCP-47 tag for the browser's speech), the input
--                   hours you had before the app
--   lang_cards      the deck: a word (front = the word, back = what it means) or a cloze sentence ({{...}} hides the
--                   answer); an example, notes, tags; its FSRS memory (stability, difficulty), when it's due
--   lang_reviews    every answer: the grade (1 Again, 2 Hard, 3 Good, 4 Easy), how it was asked, seconds taken, the
--                   card's memory before it (for Undo)
--   lang_resources  books, shows, podcasts, courses you're working through
--   lang_study      the study log: minutes of an activity (a class, a tutor, reading, listening...), with whom, notes
--   lang_cando      the CEFR can-do checklist: which statements you've ticked, and when
BEGIN;

CREATE TABLE IF NOT EXISTS lang_languages (
    language_id       serial PRIMARY KEY,
    name              text NOT NULL CHECK (btrim(name) <> ''),
    voice             text CHECK (voice ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$'),
    level             text CHECK (level IN ('A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2')),
    goal_level        text CHECK (goal_level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')),
    goal_date         date,
    why               text,
    daily_minutes     smallint NOT NULL DEFAULT 20 CHECK (daily_minutes BETWEEN 1 AND 600),
    new_per_day       smallint NOT NULL DEFAULT 10 CHECK (new_per_day BETWEEN 0 AND 200),
    prior_input_hours numeric(6, 1) NOT NULL DEFAULT 0 CHECK (prior_input_hours BETWEEN 0 AND 20000),
    active            boolean NOT NULL DEFAULT true,
    started_on        date NOT NULL DEFAULT current_date,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS lang_languages_name_uq ON lang_languages (lower(name));

CREATE TABLE IF NOT EXISTS lang_cards (
    card_id     serial PRIMARY KEY,
    language_id integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    kind        text NOT NULL DEFAULT 'word' CHECK (kind IN ('word', 'cloze')),
    front       text NOT NULL CHECK (btrim(front) <> ''),
    back        text NOT NULL CHECK (btrim(back) <> ''),
    example     text,
    example_meaning text,
    notes       text,
    tags        text[] NOT NULL DEFAULT '{}',
    state       text NOT NULL DEFAULT 'new' CHECK (state IN ('new', 'learning', 'review', 'relearning')),
    due         timestamptz NOT NULL DEFAULT now(),
    stability   real,
    difficulty  real,
    reps        integer NOT NULL DEFAULT 0,
    lapses      integer NOT NULL DEFAULT 0,
    last_review timestamptz,
    learned_on  date,
    suspended   boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT lang_cards_cloze_marked CHECK (kind <> 'cloze' OR front ~ '\{\{.+?\}\}'),
    CONSTRAINT lang_cards_memory_fit CHECK (state = 'new' OR (stability > 0 AND difficulty BETWEEN 1 AND 10))
);
CREATE INDEX IF NOT EXISTS lang_cards_language_idx ON lang_cards (language_id, due);
CREATE UNIQUE INDEX IF NOT EXISTS lang_cards_front_uq ON lang_cards (language_id, kind, lower(front));

CREATE TABLE IF NOT EXISTS lang_reviews (
    review_id     bigserial PRIMARY KEY,
    card_id       integer NOT NULL REFERENCES lang_cards ON DELETE CASCADE,
    reviewed_at   timestamptz NOT NULL DEFAULT now(),
    grade         smallint NOT NULL CHECK (grade BETWEEN 1 AND 4),
    mode          text NOT NULL DEFAULT 'flip' CHECK (mode IN ('flip', 'type', 'listen', 'cloze')),
    state_before  text NOT NULL CHECK (state_before IN ('new', 'learning', 'review', 'relearning')),
    interval_days real,
    seconds       smallint CHECK (seconds BETWEEN 0 AND 3600),
    prev          jsonb            -- the card's memory before this answer (Undo puts it back)
);
CREATE INDEX IF NOT EXISTS lang_reviews_card_idx ON lang_reviews (card_id);
CREATE INDEX IF NOT EXISTS lang_reviews_at_idx ON lang_reviews (reviewed_at);

CREATE TABLE IF NOT EXISTS lang_resources (
    resource_id serial PRIMARY KEY,
    language_id integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    title       text NOT NULL CHECK (btrim(title) <> ''),
    kind        text NOT NULL DEFAULT 'Book' CHECK (kind IN ('Book', 'Textbook', 'Show', 'Film', 'Podcast', 'YouTube', 'App',
                                                             'Course', 'Website', 'Music', 'Other')),
    status      text NOT NULL DEFAULT 'Using' CHECK (status IN ('Want', 'Using', 'Done', 'Dropped')),
    level       text CHECK (level IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')),
    url         text CHECK (url ~* '^https?://'),
    progress    text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lang_resources_language_idx ON lang_resources (language_id);

CREATE TABLE IF NOT EXISTS lang_study (
    study_id    serial PRIMARY KEY,
    language_id integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    studied_on  date NOT NULL DEFAULT current_date,
    activity    text NOT NULL CHECK (activity IN ('App', 'Class', 'Tutor', 'Reading', 'Listening', 'Watching', 'Speaking',
                                                  'Writing', 'Grammar', 'Other')),
    minutes     smallint NOT NULL CHECK (minutes BETWEEN 1 AND 1440),
    resource_id integer REFERENCES lang_resources ON DELETE SET NULL,
    with_whom   text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lang_study_language_idx ON lang_study (language_id, studied_on);
CREATE INDEX IF NOT EXISTS lang_study_resource_idx ON lang_study (resource_id);

CREATE TABLE IF NOT EXISTS lang_cando (
    language_id integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    item        text NOT NULL CHECK (item ~ '^[a-c][12]-[a-z0-9-]{2,30}$'),
    done_on     date NOT NULL DEFAULT current_date,
    PRIMARY KEY (language_id, item)
);

-- Calendar events for Golf and Language learning too (keep in step with db.MODULE_IDS): classes, tutor sessions.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%language%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl', 'sudoku', 'golf', 'language'));
    END IF;
END $$;

COMMIT;
