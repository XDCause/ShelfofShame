-- Volleyball byes (2026-10-15).
--
-- A round with no opponent: volleyball_games.bye = 'win' (a bye counted as a win, as competition
-- ladders do) or 'no result'. A bye has no opponent or sets.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE volleyball_games ADD COLUMN IF NOT EXISTS bye TEXT CHECK (bye IN ('win', 'no result'));
