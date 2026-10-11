-- Hobby supplies inventory: lookup values
-- Runs once, after 01_schema.sql, when the database volume is first created.
-- Real supplies are loaded afterwards by scripts/import_spreadsheet.py.

BEGIN;

INSERT INTO categories (name) VALUES
    ('Paint'),
    ('Primer / Surfacer'),
    ('Thinner'),
    ('Clear / Varnish'),
    ('Masking Tape'),
    ('Masking Fluid / Putty'),
    ('Glue / Cement'),
    ('Putty / Filler'),
    ('Weathering'),
    ('Pigments'),
    ('Decals'),
    ('Decal Solution'),
    ('Brushes'),
    ('Airbrush & Parts'),
    ('Sanding / Abrasives'),
    ('Tools'),
    ('Photo-etch / Aftermarket'),
    ('Basing Materials'),
    ('Cleaning Supplies'),
    ('Other');

-- Only brands actually used (matches the spreadsheet's Lists tab). Add more as you buy them.
INSERT INTO brands (name) VALUES
    ('Tamiya'),
    ('Milliput'),
    ('Microscale'),
    ('Other');

INSERT INTO storage_locations (name) VALUES
    ('Paint rack'),
    ('Drawer 1'),
    ('Drawer 2'),
    ('Workbench'),
    ('Storage box'),
    ('Shelf'),
    ('Other');

COMMIT;
