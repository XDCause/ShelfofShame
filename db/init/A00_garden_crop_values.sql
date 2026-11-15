-- Garden: what a harvest would cost at the shop, so the Harvests page can say whether a crop was worth growing
-- (the hiking and shooting additions need no tables). Idempotent.
--   garden_crop_values   one row per crop (a planting's name, lower case) and harvest unit: the shop price of one unit
--                        (e.g. cherry tomatoes, g -> 0.012 dollars a gram). You enter it; nothing is looked up.
BEGIN;

CREATE TABLE IF NOT EXISTS garden_crop_values (
    crop        text NOT NULL CHECK (crop = lower(btrim(crop)) AND crop <> ''),
    unit        text NOT NULL CHECK (unit = lower(btrim(unit)) AND unit <> ''),
    per_unit    numeric(10, 4) NOT NULL CHECK (per_unit >= 0),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (crop, unit)
);

COMMIT;
