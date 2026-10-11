-- Hobby supplies inventory: schema
-- Runs once, automatically, when the database volume is first created.

BEGIN;

-- ---------------------------------------------------------------------------
-- Lookup tables: each name stored once, referenced by id from supplies.
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE brands (
    brand_id SERIAL PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE
);

CREATE TABLE storage_locations (
    location_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Main table
-- ---------------------------------------------------------------------------
CREATE TABLE supplies (
    supply_id      SERIAL PRIMARY KEY,
    brand_id       INT REFERENCES brands (brand_id),
    product_code   TEXT,                       -- e.g. XF-1, C-33, T-106
    name           TEXT NOT NULL,              -- item / colour name
    category_id    INT NOT NULL REFERENCES categories (category_id),
    paint_type     TEXT CHECK (paint_type IN
                       ('Acrylic', 'Lacquer', 'Enamel', 'Water-based', 'Oil', 'Alcohol-based', 'N/A')),
    finish         TEXT CHECK (finish IN
                       ('Flat / Matt', 'Satin', 'Semi-gloss', 'Gloss', 'Metallic', 'Clear',
                        'Pearl', 'Fluorescent', 'N/A')),
    size           TEXT,                       -- free text: 10ml, 400ml, 18m, 10mm...
    qty_on_hand    INT NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
    reorder_at     INT CHECK (reorder_at >= 0), -- NULL = never flag as low
    condition      TEXT CHECK (condition IN
                       ('Sealed', 'Opened', 'Half used', 'Nearly empty', 'Empty', 'Dried out')),
    unit_price     NUMERIC(10, 2) CHECK (unit_price >= 0),
    purchase_date  DATE,
    purchased_from TEXT,
    location_id    INT REFERENCES storage_locations (location_id),
    used_for       TEXT,                       -- project
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT supplies_brand_code_uq UNIQUE (brand_id, product_code)
);

-- Speed up the common filters/joins.
CREATE INDEX supplies_category_idx ON supplies (category_id);
CREATE INDEX supplies_location_idx ON supplies (location_id);

-- ---------------------------------------------------------------------------
-- Keep updated_at current on every UPDATE, no matter who does the update.
-- ---------------------------------------------------------------------------
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER supplies_set_updated_at
    BEFORE UPDATE ON supplies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Friendly read view: names instead of ids, plus calculated columns.
-- ---------------------------------------------------------------------------
CREATE VIEW v_supplies AS
SELECT
    s.supply_id,
    'SUP-' || lpad(s.supply_id::text, 4, '0') AS item_ref,
    b.name  AS brand,
    s.product_code,
    s.name,
    c.name  AS category,
    s.paint_type,
    s.finish,
    s.size,
    s.qty_on_hand,
    s.reorder_at,
    CASE
        WHEN s.qty_on_hand <= 0            THEN 'Out'
        WHEN s.qty_on_hand <= s.reorder_at THEN 'Low'
        ELSE 'OK'
    END AS stock_status,
    s.condition,
    s.unit_price,
    s.qty_on_hand * s.unit_price AS total_value,
    s.purchase_date,
    s.purchased_from,
    l.name  AS location,
    s.used_for,
    s.notes,
    s.created_at,
    s.updated_at
FROM supplies s
JOIN      categories        c ON c.category_id = s.category_id
LEFT JOIN brands            b ON b.brand_id    = s.brand_id
LEFT JOIN storage_locations l ON l.location_id = s.location_id;

COMMIT;
