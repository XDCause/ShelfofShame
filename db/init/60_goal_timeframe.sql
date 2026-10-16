-- Goals for a set time: a year's goals (New Year's goals) or a 3-year goal.
--   timeframe     'year' | 'three_years' | NULL (no set time)
--   period_start  the year it's for (a 3-year goal covers period_start .. period_start + 2)
-- Idempotent: safe to run again.
ALTER TABLE goals ADD COLUMN IF NOT EXISTS timeframe TEXT;
ALTER TABLE goals ADD COLUMN IF NOT EXISTS period_start INT;
ALTER TABLE goals DROP CONSTRAINT IF EXISTS goals_timeframe_check;
ALTER TABLE goals ADD CONSTRAINT goals_timeframe_check
    CHECK (timeframe IN ('year', 'three_years') AND period_start BETWEEN 2000 AND 2200
           OR timeframe IS NULL AND period_start IS NULL);
