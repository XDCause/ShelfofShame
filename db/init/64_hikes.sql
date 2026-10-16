-- Hiking: one row per hike - imported from a GPX file (AllTrails' export, or any GPS app's) or logged
-- by hand. The numbers (distance, climb, times, splits) are worked out from the GPS track when it's
-- imported (api/app/gpx.py); the original file is kept so it can be downloaded again. Idempotent.
CREATE TABLE IF NOT EXISTS hikes (
    hike_id       serial PRIMARY KEY,
    name          text NOT NULL CHECK (btrim(name) <> ''),
    hiked_on      date NOT NULL,
    started_at    timestamptz,
    ended_at      timestamptz,
    distance_m    numeric(9, 1) CHECK (distance_m >= 0),
    moving_s      integer CHECK (moving_s >= 0),
    elapsed_s     integer CHECK (elapsed_s >= 0),
    ascent_m      numeric(7, 1) CHECK (ascent_m >= 0),
    descent_m     numeric(7, 1) CHECK (descent_m >= 0),
    max_ele_m     numeric(7, 1),
    min_ele_m     numeric(7, 1),
    start_lat     double precision,
    start_lon     double precision,
    is_loop       boolean,
    points        integer,                 -- GPS points in the file
    track         jsonb,                   -- [[lat, lon, ele, seconds from start, metres from start], ...] (thinned)
    splits        jsonb,                   -- [{km, metres, seconds, ascent, descent}, ...]
    waypoints     jsonb,                   -- [{name, lat, lon, ele}, ...]
    trail_name    text,
    trail_url     text CHECK (trail_url IS NULL OR trail_url ~ '^https?://'),
    location      text,
    difficulty    text CHECK (difficulty IN ('Easy', 'Moderate', 'Hard')),
    rating        smallint CHECK (rating BETWEEN 1 AND 5),
    companions    text,
    weather       text,
    notes         text,
    source        text NOT NULL DEFAULT 'manual' CHECK (source IN ('gpx', 'manual')),
    gpx_name      text,                    -- the file's name
    gpx_hash      text,                    -- sha256 of the file: the same file isn't imported twice
    gpx           bytea,
    landmarks     jsonb,                   -- peaks, lookouts, huts... near the track (OpenStreetMap, overpass.py)
    nearby_photos jsonb,                   -- photos people took near the track (Wikimedia Commons, wikimedia.py)
    landmarks_at  timestamptz,             -- when they were last looked up
    landmarks_error text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT hikes_gpx_hash_uq UNIQUE (gpx_hash),
    CONSTRAINT hikes_time_check CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX IF NOT EXISTS hikes_hiked_on_idx ON hikes (hiked_on DESC);

CREATE TABLE IF NOT EXISTS hike_photos (
    photo_id   serial PRIMARY KEY,
    hike_id    integer NOT NULL REFERENCES hikes ON DELETE CASCADE,
    image      bytea NOT NULL,
    image_type text NOT NULL,
    taken_at   timestamptz,                -- from the photo's EXIF (read in the browser)
    lat        double precision,
    lon        double precision,
    along_m    numeric(9, 1),              -- how far along the track it was taken
    located    text CHECK (located IN ('gps', 'time')),   -- placed by its own GPS, or by its time on the track
    caption    text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS hike_photos_hike_idx ON hike_photos (hike_id);
