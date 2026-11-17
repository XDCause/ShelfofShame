-- The last good forecast, and a history of the website checks (2026-11-17). Safe to run twice.
--   weather_kept     Open-Meteo's last good answer per place and kind (openmeteo.py): shown, with its time, while
--                    Open-Meteo can't be reached - its forecast server stopped answering this network on 2026-11-16
--   site_check_log   every website check's result (sitecheck.run_all), a year kept: how often a site fails
BEGIN;

CREATE TABLE IF NOT EXISTS weather_kept (
    place_key  TEXT PRIMARY KEY,                     -- "-27.47,153.03,3" (lat, lon, which forecast)
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    data       JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS site_check_log (
    log_id     BIGSERIAL PRIMARY KEY,
    site       TEXT NOT NULL,
    ok         BOOLEAN NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail     TEXT
);
CREATE INDEX IF NOT EXISTS site_check_log_site_when ON site_check_log (site, checked_at);

COMMIT;
