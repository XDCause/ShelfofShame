-- The weekly check of the websites the app reads (api/app/sitecheck.py): one row per site.
--   ok             the last check worked and the answer looked as expected
--   detail         what it found ("XF-1 Flat Black, with a photo") or why it failed
--   failing_since  when it started failing (NULL while it works) - so a site that changed is noticed
-- Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS site_checks (
    site           TEXT PRIMARY KEY,
    ok             BOOLEAN NOT NULL,
    detail         TEXT,
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    failing_since  TIMESTAMPTZ
);
