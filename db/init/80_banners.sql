-- Page banners (2026-10-20): each main page (Home, the journal, the calendar...) and each hobby opens with a banner -
-- a picture of your own, if you've given it one, or a drawn landscape in the hobby's colour (web/src/components/
-- Landscape.jsx). One row per area; the photo is yours (never in the repo). Idempotent.
CREATE TABLE IF NOT EXISTS banners (
    banner_id     serial PRIMARY KEY,
    area          text NOT NULL UNIQUE CHECK (area ~ '^[a-z]{2,30}$'),   -- 'home', 'journal', or a hobby's id ('models')
    photo         bytea,
    photo_type    text,
    photo_updated timestamptz,
    -- where the picture sits in the banner (0 = top, 100 = bottom), so a landscape's horizon lines up
    focus_y       smallint NOT NULL DEFAULT 50 CHECK (focus_y BETWEEN 0 AND 100)
);
