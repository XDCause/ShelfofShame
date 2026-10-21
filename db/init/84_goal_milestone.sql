-- A yes / no goal (2026-10-21, user: "in 3 years I want to have proposed - it's a yes or no, so Behind isn't true"):
-- goals.kind 'milestone' - done or not yet, no number and no pace. Its to-dos (if any) still show how far the steps
-- are. Idempotent.

ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_kind_check;
ALTER TABLE goals ADD CONSTRAINT goals_kind_check CHECK (kind IN ('target', 'habit', 'milestone'));
