-- Precision shooting, live board (2026-10-19): a shot can be a hit or a miss (steel, a scoring zone, a gong), and a
-- group says what it was shot at and how many hit (worked out from its shots, or typed). Idempotent.
ALTER TABLE shooting_shots ADD COLUMN IF NOT EXISTS hit boolean;                       -- null = not called
ALTER TABLE shooting_groups ADD COLUMN IF NOT EXISTS target text;                      -- "2 MOA steel", "Gong 300 mm"
ALTER TABLE shooting_groups ADD COLUMN IF NOT EXISTS hits integer CHECK (hits >= 0);
