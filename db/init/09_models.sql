-- Models (kits) and the paints each one needs (2026-10-11).
--
-- A model's paints are matched to your inventory by brand + product code - not to one
-- particular bottle - so the checklist stays right when a bottle is used up and replaced.
-- A model's photo uses the same product_info cache as supplies (brand + kit code).
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\09_models.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE TABLE IF NOT EXISTS models (
    model_id     SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,                 -- e.g. Mitsubishi A6M3 Zero
    brand_id     INT REFERENCES brands (brand_id),
    product_code TEXT,                          -- kit code, e.g. T61108 (photo + tamiya.com link)
    scale        TEXT,                          -- e.g. 1/48
    status       TEXT NOT NULL DEFAULT 'Not started'
                 CHECK (status IN ('Not started', 'In progress', 'On hold', 'Finished')),
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_paints (
    model_paint_id SERIAL PRIMARY KEY,
    model_id       INT NOT NULL REFERENCES models (model_id) ON DELETE CASCADE,
    brand_id       INT REFERENCES brands (brand_id),   -- with product_code: how it's matched
    product_code   TEXT,                               --   to your inventory (e.g. Tamiya T81776)
    paint_name     TEXT NOT NULL,                      -- e.g. XF-76 Grey Green (IJN)
    purpose        TEXT,                               -- what it's for on this model
    have_it        BOOLEAN NOT NULL DEFAULT false,     -- ticked by hand (for paints you don't track);
                                                       -- paints in your inventory count as ticked anyway
    sort_order     INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_paints_model_idx ON model_paints (model_id, sort_order);

DROP TRIGGER IF EXISTS models_set_updated_at ON models;
CREATE TRIGGER models_set_updated_at
    BEFORE UPDATE ON models
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
