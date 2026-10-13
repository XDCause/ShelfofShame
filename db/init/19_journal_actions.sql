-- Acting on what a journal page says (2026-10-13).
--
-- A page that mentions a model with words like "started" or "primed" gets suggestions
-- ("Sherman -> In progress"), applied with one tap (api/app/journal_actions.py). A suggestion you
-- wave away is remembered here, on the page, so it stays away on every device.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS dismissed TEXT[] NOT NULL DEFAULT '{}';
