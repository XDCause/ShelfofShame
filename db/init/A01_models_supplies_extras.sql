-- Models and supplies extras (2026-11-16). Idempotent.
--   paint_recipes / paint_recipe_steps  a named recipe: ordered steps (base, wash, highlight...), each with a paint from
--                                       your supplies (brand + code, matched like a model's paint list) or free text, and
--                                       a note. It can sit on a model (and a unit / mini name) or on its own.
--   model_sessions.stage                the model's build step when the session was started (set by a trigger), so time
--                                       can be added up per step
-- No (kind, ref) rows here, so no delete trigger: steps go with their recipe (ON DELETE CASCADE) and a deleted model
-- leaves its recipes behind on their own (ON DELETE SET NULL).
BEGIN;

CREATE TABLE IF NOT EXISTS paint_recipes (
    recipe_id  SERIAL PRIMARY KEY,
    name       TEXT NOT NULL CHECK (btrim(name) <> ''),
    notes      TEXT,
    model_id   INT REFERENCES models (model_id) ON DELETE SET NULL,
    unit       TEXT,                                   -- a mini or unit of that model ("Skitarii Rangers"); optional
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS paint_recipes_model_idx ON paint_recipes (model_id);

CREATE TABLE IF NOT EXISTS paint_recipe_steps (
    step_id      SERIAL PRIMARY KEY,
    recipe_id    INT NOT NULL REFERENCES paint_recipes (recipe_id) ON DELETE CASCADE,
    sort_order   INT NOT NULL DEFAULT 0,
    label        TEXT,                                 -- base, layer, wash, highlight...
    paint_text   TEXT NOT NULL CHECK (btrim(paint_text) <> ''),
    brand_id     INT REFERENCES brands (brand_id),     -- with product_code: matched to your supplies
    product_code TEXT,
    note         TEXT
);
CREATE INDEX IF NOT EXISTS paint_recipe_steps_idx ON paint_recipe_steps (recipe_id, sort_order);

DROP TRIGGER IF EXISTS paint_recipes_set_updated_at ON paint_recipes;
CREATE TRIGGER paint_recipes_set_updated_at
    BEFORE UPDATE ON paint_recipes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE model_sessions ADD COLUMN IF NOT EXISTS stage TEXT;   -- NULL = before this was recorded

CREATE OR REPLACE FUNCTION model_session_stage() RETURNS trigger AS $$
BEGIN
    IF NEW.stage IS NULL THEN
        SELECT COALESCE(m.stage, 'Not built') INTO NEW.stage FROM models m WHERE m.model_id = NEW.model_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS model_sessions_stage ON model_sessions;
CREATE TRIGGER model_sessions_stage
    BEFORE INSERT ON model_sessions
    FOR EACH ROW EXECUTE FUNCTION model_session_stage();

COMMIT;
