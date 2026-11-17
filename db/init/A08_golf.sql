-- Golf (2026-11-17), a hobby module (api/app/golf.py, golf_rounds.py, golfmath.py; web/src/modules/golf). Idempotent.
--   golf_settings       one row: your official GA Handicap (typed from GolfLink, or the app's estimate is used), the daily
--                       handicap allowance (Golf Australia's x 0.93), the handicap you're aiming for
--   golf_courses        a course: by hand, or from OpenStreetMap (osm = 'way/123': its holes, greens, tees, bunkers, water)
--   golf_holes          each hole's par, stroke index and map (OpenStreetMap shapes as [[lat, lon], ...])
--   golf_tees           a set of tees: its scratch rating and slope (typed: Golf Australia's course ratings), and
--   golf_hole_lengths   each hole's length from those tees
--   golf_clubs          what's in your bag (with the carry you'd say; the measured one comes from golf_shots)
--   golf_rounds         a round: course, tees, 18 / front / back, format, your handicap and daily handicap when you teed off
--   golf_round_holes    each hole's score: strokes, putts, fairway, penalties, bunker shots, first putt's length
--   golf_shots          shots marked on the course (GPS + club + lie): club distances and strokes gained
--   golf_practice       range / putting / chipping sessions, with a drill's score
BEGIN;

CREATE TABLE IF NOT EXISTS golf_settings (
    id                integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    official_handicap numeric(3, 1) CHECK (official_handicap BETWEEN -10 AND 54),
    official_as_of    date,
    allowance         numeric(4, 3) NOT NULL DEFAULT 0.93 CHECK (allowance BETWEEN 0.5 AND 1),
    target_handicap   numeric(3, 1) CHECK (target_handicap BETWEEN -10 AND 54),
    home_course_id    integer,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
INSERT INTO golf_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS golf_courses (
    course_id  serial PRIMARY KEY,
    name       text NOT NULL CHECK (btrim(name) <> ''),
    place      text,
    lat        double precision CHECK (lat BETWEEN -90 AND 90),
    lon        double precision CHECK (lon BETWEEN -180 AND 180),
    holes      smallint NOT NULL DEFAULT 18 CHECK (holes IN (9, 18)),
    osm        text UNIQUE CHECK (osm ~ '^(way|relation)/[0-9]+$'),
    website    text,
    notes      text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS golf_holes (
    course_id    integer NOT NULL REFERENCES golf_courses ON DELETE CASCADE,
    hole_no      smallint NOT NULL CHECK (hole_no BETWEEN 1 AND 18),
    par          smallint NOT NULL DEFAULT 4 CHECK (par BETWEEN 3 AND 6),
    stroke_index smallint CHECK (stroke_index BETWEEN 1 AND 18),
    map          jsonb,
    PRIMARY KEY (course_id, hole_no)
);

CREATE TABLE IF NOT EXISTS golf_tees (
    tee_id    serial PRIMARY KEY,
    course_id integer NOT NULL REFERENCES golf_courses ON DELETE CASCADE,
    name      text NOT NULL CHECK (btrim(name) <> ''),
    colour    text CHECK (colour ~ '^#[0-9a-fA-F]{6}$'),
    gender    text NOT NULL DEFAULT 'Men' CHECK (gender IN ('Men', 'Women')),
    rating    numeric(4, 1) CHECK (rating BETWEEN 25 AND 85),
    slope     smallint CHECK (slope BETWEEN 55 AND 155),
    position  smallint NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS golf_tees_course_idx ON golf_tees (course_id);

CREATE TABLE IF NOT EXISTS golf_hole_lengths (
    tee_id  integer NOT NULL REFERENCES golf_tees ON DELETE CASCADE,
    hole_no smallint NOT NULL CHECK (hole_no BETWEEN 1 AND 18),
    metres  smallint NOT NULL CHECK (metres BETWEEN 30 AND 800),
    PRIMARY KEY (tee_id, hole_no)
);

CREATE TABLE IF NOT EXISTS golf_clubs (
    club_id  serial PRIMARY KEY,
    name     text NOT NULL CHECK (btrim(name) <> ''),
    kind     text NOT NULL CHECK (kind IN ('Driver', 'Wood', 'Hybrid', 'Iron', 'Wedge', 'Putter')),
    loft     numeric(3, 1) CHECK (loft BETWEEN 0 AND 70),
    carry_m  smallint CHECK (carry_m BETWEEN 1 AND 400),
    brand    text,
    in_bag   boolean NOT NULL DEFAULT true,
    position smallint NOT NULL DEFAULT 0,
    notes    text
);

CREATE TABLE IF NOT EXISTS golf_rounds (
    round_id       serial PRIMARY KEY,
    course_id      integer NOT NULL REFERENCES golf_courses ON DELETE RESTRICT,
    tee_id         integer REFERENCES golf_tees ON DELETE SET NULL,
    played_on      date NOT NULL DEFAULT current_date,
    holes          text NOT NULL DEFAULT '18' CHECK (holes IN ('18', 'front', 'back')),
    format         text NOT NULL DEFAULT 'Stableford' CHECK (format IN ('Stableford', 'Stroke', 'Par', 'Ambrose', 'Social')),
    counts         boolean NOT NULL DEFAULT true,
    handicap       numeric(3, 1) CHECK (handicap BETWEEN -10 AND 54),
    daily_handicap smallint CHECK (daily_handicap BETWEEN -15 AND 70),
    status         text NOT NULL DEFAULT 'playing' CHECK (status IN ('playing', 'done')),
    competition    text,
    partners       text,
    notes          text,
    weather        jsonb,
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz,
    CONSTRAINT golf_rounds_done_check CHECK ((status = 'done') = (finished_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS golf_rounds_course_idx ON golf_rounds (course_id);
CREATE INDEX IF NOT EXISTS golf_rounds_tee_idx ON golf_rounds (tee_id);
CREATE INDEX IF NOT EXISTS golf_rounds_played_idx ON golf_rounds (played_on);

CREATE TABLE IF NOT EXISTS golf_round_holes (
    round_id     integer NOT NULL REFERENCES golf_rounds ON DELETE CASCADE,
    hole_no      smallint NOT NULL CHECK (hole_no BETWEEN 1 AND 18),
    strokes      smallint CHECK (strokes BETWEEN 1 AND 20),
    putts        smallint CHECK (putts BETWEEN 0 AND 10),
    fairway      text CHECK (fairway IN ('hit', 'left', 'right', 'short', 'long')),
    penalties    smallint NOT NULL DEFAULT 0 CHECK (penalties BETWEEN 0 AND 10),
    sand         smallint NOT NULL DEFAULT 0 CHECK (sand BETWEEN 0 AND 10),
    first_putt_m numeric(4, 1) CHECK (first_putt_m BETWEEN 0 AND 99),
    picked_up    boolean NOT NULL DEFAULT false,
    PRIMARY KEY (round_id, hole_no),
    CONSTRAINT golf_round_holes_counts_fit CHECK (putts IS NULL OR strokes IS NULL OR putts + penalties <= strokes),
    CONSTRAINT golf_round_holes_picked_check CHECK (NOT (picked_up AND strokes IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS golf_shots (
    shot_id    bigserial PRIMARY KEY,
    round_id   integer NOT NULL REFERENCES golf_rounds ON DELETE CASCADE,
    hole_no    smallint NOT NULL CHECK (hole_no BETWEEN 1 AND 18),
    seq        smallint NOT NULL CHECK (seq BETWEEN 1 AND 20),
    club_id    integer REFERENCES golf_clubs ON DELETE SET NULL,
    lie        text NOT NULL CHECK (lie IN ('tee', 'fairway', 'rough', 'sand', 'recovery')),
    lat        double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon        double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
    accuracy_m real,
    taken_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT golf_shots_seq_key UNIQUE (round_id, hole_no, seq)
);
CREATE INDEX IF NOT EXISTS golf_shots_club_idx ON golf_shots (club_id);

CREATE TABLE IF NOT EXISTS golf_practice (
    practice_id  serial PRIMARY KEY,
    practiced_on date NOT NULL DEFAULT current_date,
    kind         text NOT NULL CHECK (kind IN ('Range', 'Putting', 'Chipping', 'Bunker', 'Lesson', 'Simulator', 'Course')),
    minutes      smallint CHECK (minutes BETWEEN 1 AND 600),
    balls        smallint CHECK (balls BETWEEN 1 AND 2000),
    focus        text,
    drill        text,
    made         smallint CHECK (made >= 0),
    attempts     smallint CHECK (attempts BETWEEN 1 AND 1000),
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT golf_practice_made_fit CHECK (made IS NULL OR (attempts IS NOT NULL AND made <= attempts))
);
CREATE INDEX IF NOT EXISTS golf_practice_on_idx ON golf_practice (practiced_on);

-- Calendar events for the Golf hobby too (keep in step with db.MODULE_IDS): tee times.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%golf%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl', 'sudoku', 'golf'));
    END IF;
END $$;

COMMIT;
