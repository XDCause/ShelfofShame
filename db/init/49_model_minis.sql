-- Each mini in a Warhammer box with its own build step (the box's step and "minis painted" are then
-- worked out from them). Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS model_minis (
    mini_id     SERIAL PRIMARY KEY,
    model_id    INT NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
    unit        TEXT NOT NULL CHECK (btrim(unit) <> ''),   -- "Skitarii Rangers"
    name        TEXT,                                     -- "Alpha", "Plasma caliver" - optional
    stage       TEXT,                                     -- last build step done; NULL = not started
    sort_order  INT NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_minis_model_idx ON model_minis (model_id);

-- What's in a box, read from the shop's description: [{"unit": "Skitarii Rangers", "count": 10}, ...]
ALTER TABLE product_info ADD COLUMN IF NOT EXISTS kit_units JSONB;
