# Shelf of Shame

A self-hosted inventory for model-kit supplies (paints, thinners, tape, glue, tools...), built
as a full-stack learning project. Runs entirely in Docker on your own PC; no accounts or
subscriptions.

- **Inventory**: search, filter, sort, grouped into drop-downs (by category, condition, brand...; remembered), photos, +/- with Undo, per-item stock history, "used on"
  (which models need it), colour matches, and "used up, not replacing it" removal
- **Wishlist**: phone-friendly shopping list; tick things off in the shop, then move them into
  inventory in one go. **Shop Tamiya** searches ~1,000 Tamiya products and adds one in a tap
- **Barcode scanning** from a phone photo (decoded in the browser), with a built-in catalogue
  of Tamiya Acrylic Mini paint barcodes
- **Tamiya lookup**: type an item number or paint code (e.g. `XF-76`) to fill in the name,
  photo, size, paint type, finish and your usual price
- **Models (kit stash)**: Wanted / In stash / In progress / On hold / Finished / Gone, what you
  paid, a "shelf of shame" total, a paint checklist (ticked automatically for paints you own,
  suggests a matching paint you do own), paints picked straight from a Tamiya kit's own paint
  list, a timer and time log, and a build log with photos
- **Colours**: matches between Tamiya ranges (same code, same colour name), your own matches
  between any brands, and mixes ("XF-62 + XF-2 (3:1)") that work on model paint lists
- **Settings**: spending (lifetime / year / month), price guide, default shop, backups (back up
  now, download), CSV export for Excel, Tamiya catalogue refresh, brands / categories / locations
- Styled after Apple's Human Interface Guidelines (bottom tab bar and sheets on phones, dark mode)
- Nightly backups, 159 automated API tests and a 38-step browser walkthrough

Three Docker containers:

| Container | What it is | Address on this PC |
|---|---|---|
| `hobby-inventory-web` | React app (built with Vite), served by nginx; forwards `/api/*` to the API | http://localhost:8080 |
| `hobby-inventory-api` | FastAPI backend, the only thing that talks to the database | http://localhost:8000/api/docs |
| `hobby-inventory-db` | PostgreSQL 17 | `localhost:5433` (DBeaver) |

```
Browser -> web (nginx) -> api (FastAPI) -> db (PostgreSQL)
```

## API endpoints

Grouped as in `api/app/` (one module per part of the app):

| Method | Path | Does |
|---|---|---|
| **supplies.py** | | |
| GET | `/api/supplies?q=&category=&brand=&status=&location=` | Search / filter (each with `used_on` models) |
| GET | `/api/supplies/low-stock` | Everything Low or Out |
| GET/PATCH | `/api/supplies/{id}` | One supply / change some fields |
| POST | `/api/supplies` | Add a supply |
| POST | `/api/supplies/{id}/adjust` | `{"delta": -1}` = used one, `{"delta": 2}` = bought two |
| DELETE | `/api/supplies/{id}?also_wishlist=true` | Remove (used up, not replacing it) |
| POST | `/api/supplies/{id}/wishlist` | Put one supply on the wishlist |
| GET | `/api/supplies/{id}/history`, `/api/history` | Quantity changes (with the price at the time) |
| **wishlist.py** | | |
| GET/POST | `/api/wishlist` | Wishlist, with photos and "you own N" / add an item |
| PATCH/DELETE | `/api/wishlist/{id}` | Edit (`{"got_it": true}` ticks it off) / remove |
| POST | `/api/wishlist/{id}/buy`, `/api/wishlist/buy-ticked` | Bought: move to inventory (blank shop = your default shop) |
| POST | `/api/wishlist/restock` | Everything Out or Low onto the wishlist |
| **products.py** | | |
| GET | `/api/lookup/tamiya/{item}` | Product details + photo from tamiya.com (cached after first time) |
| GET | `/api/lookup/hasegawa/{code}` | Hasegawa kit by series code (`JT86`) or item number (`09086`) |
| GET | `/api/scan/{barcode}` | Identify an item from its barcode (known / catalog / Tamiya / unknown) |
| PUT | `/api/product-barcode` | Remember a barcode `{"brand_id", "product_code", "barcode"}` |
| PUT/DELETE | `/api/product-photo?brand_id=&product_code=` | Your own photo for any item (image as the body) |
| GET | `/api/product-images/{id}` | A cached product photo |
| **catalog.py** (Shop Tamiya) | | |
| GET | `/api/catalog/search?q=panel line black` | Search the Tamiya catalogue |
| POST | `/api/catalog/{product_code}/wishlist` | Onto the wishlist (details + photo fetched in the background) |
| GET | `/api/catalog/info` · POST `/api/catalog/refresh` | Size / refresh from tamiya.com (~3 min, in the background) |
| **models.py** | | |
| GET/POST | `/api/models` | List / add kits |
| GET | `/api/models/summary` | Shelf of shame (unbuilt kits and their cost), counts per status, hours |
| GET/PATCH/DELETE | `/api/models/{id}` | One kit with its checklist, sessions and build log |
| POST | `/api/models/{id}/paints` | Add paints: `XF-76 Grey Green\tExterior`, or a mix `XF-62 + XF-2 (3:1)` |
| PATCH/DELETE | `/api/model-paints/{id}` | Edit / remove a checklist line |
| GET/POST | `/api/models/{id}/kit-paints` | Tamiya's "Colors required" for the kit / add the ones you picked |
| POST | `/api/models/{id}/wishlist` | Missing paints (and missing parts of mixes) onto the wishlist |
| **build.py** | | |
| POST | `/api/models/{id}/timer/start`, `.../timer/stop` · GET `/api/timer` | Time tracking (one timer at a time) |
| POST | `/api/models/{id}/sessions` · DELETE `/api/model-sessions/{id}` | Time added by hand |
| POST | `/api/models/{id}/log` · PATCH/DELETE `/api/model-log/{id}` | Build log entries |
| PUT/GET | `/api/model-log/{id}/photo` | A build log photo |
| **colours.py** | | |
| GET | `/api/colours/matches?brand_id=&product_code=` | Same code / same name / your matches |
| GET/POST, PATCH/DELETE | `/api/colour-groups`, `/api/colour-groups/{id}` | Your own matches (any brand) |
| GET/POST, PATCH/DELETE | `/api/mixes`, `/api/mixes/{id}` | Mixes `{"recipe": "XF-62 + XF-2 (3:1)"}` |
| **spending.py** | | |
| GET | `/api/spending` | Lifetime / year / month spend, latest purchases, kits |
| GET | `/api/export/{inventory,wishlist,models,model-paints,history}.csv` | CSV for Excel |
| **settings.py** | | |
| GET/PATCH | `/api/settings` | Default shop |
| GET/POST, PATCH/DELETE | `/api/price-guide`, `/api/price-guide/{id}` | Your usual prices |
| GET/POST | `/api/backups` · GET `/api/backups/{name}` | List / back up now / download |
| **lookups.py** | | |
| GET | `/api/lookups` | Brands, categories, locations (with usage counts) + fixed choice lists |
| POST/DELETE | `/api/lookups/{brands,categories,locations}[/{id}]` | Add / remove a list entry |

Try them interactively at http://localhost:8000/api/docs ("Try it out").

## First-time setup

1. Install and start Docker Desktop.
2. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD`.
3. Run `.\start.ps1`
4. Create the Python environment and import the spreadsheet:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\import_spreadsheet.py "C:\Users\xdhar\Downloads\Hobby_Supplies_Inventory.xlsx"
```

The import reads the **Supplies** and **Lists** sheets, is safe to re-run (it updates existing
items matched on brand + product code instead of duplicating them), and keeps the spreadsheet's
SUP-0001... numbering.

## Everyday commands (run in this folder)

| Task | Command |
|---|---|
| Start (build if needed, wait until healthy) | `.\start.ps1` |
| Start (plain) | `docker compose up -d` |
| Stop (data is kept) | `docker compose stop` |
| Stop and remove container (data is kept) | `docker compose down` |
| Status / health | `docker compose ps` |
| Logs (follow, Ctrl+C to quit) | `docker compose logs -f api` (or `db`, `web`) |
| Rebuild after changing api/ or web/ code | `docker compose up -d --build api web` |
| Interactive psql | `docker exec -it hobby-inventory-db psql -U hobby -d hobby_inventory` |
| One-off query | `docker exec hobby-inventory-db psql -U hobby -d hobby_inventory -c "SELECT * FROM v_supplies"` |
| **Wipe and rebuild** (deletes all data!) | `docker compose down -v`, `.\start.ps1`, then re-run the import |
| Update the Tamiya paint barcode catalogue (new colours) | `docker exec hobby-inventory-api python -m app.catalog_import` |
| Update the Shop Tamiya product list (~1,000 products, ~3 min) | Settings > Tamiya catalogue > Refresh (or `docker exec hobby-inventory-api python -m app.tamiya_catalog`) |
| Back up now (also runs nightly at 2 am) | Settings > Backups > Back up now, or `.\backup.ps1` (keeps the newest 14 in `backups\`) |
| Back up and copy elsewhere | `.\backup.ps1 -CopyTo "D:\Backups"` |
| Run the automated tests (never touches real data) | `.\run_tests.ps1` (or `.\run_tests.ps1 -k wishlist`) |
| Click through the whole app in a browser (desktop + iPhone) | `.\run_e2e.ps1` (backs up, runs, restores; screenshots in `e2e\out\`) |

## Restoring a backup

Replaces the current data with the backup's:

```powershell
docker cp .\backups\hobby_inventory_YYYYMMDD_HHMMSS.dump hobby-inventory-db:/tmp/restore.dump
docker exec hobby-inventory-db pg_restore -U hobby -d hobby_inventory --clean --if-exists /tmp/restore.dump
```

The nightly backup is the Windows scheduled task **"Shelf of Shame backup"** (Task Scheduler);
results are logged in `backups\backup.log`.

Useful psql commands: `\dt` list tables, `\dv` list views, `\d supplies` describe a table, `\q` quit.

## Important: init scripts only run once

`db/init/*.sql` runs **only when the data volume `hobby_pgdata` is empty**, i.e. the very
first start. Editing those files later does nothing to an existing database. To apply
changes, either run the SQL yourself (DBeaver/psql) or wipe and rebuild (above). Once your
real data is in, back it up before wiping:

```powershell
docker exec hobby-inventory-db pg_dump -U hobby -d hobby_inventory > backup.sql
```

## Connecting (DBeaver etc.)

Host `localhost`, port from `.env` (`POSTGRES_PORT`, default 5433), database `hobby_inventory`,
user `hobby`, password from `.env`. The port is bound to 127.0.0.1, so only this PC can connect.

In DBeaver make sure the **Database** field says `hobby_inventory`. If it says `postgres` you are
connected to Postgres's empty default database and will see no tables.

## Front-end development with hot reload (optional)

Rebuilding the web container takes a minute per change. For quicker UI work, install Node.js 22,
then in `web/` run `npm install` and `npm run dev`, and open http://localhost:5173. Edits show
instantly, and `/api` calls go to the API container on port 8000 (see `web/vite.config.js`).

## If PowerShell refuses to run start.ps1

`powershell -ExecutionPolicy Bypass -File .\start.ps1`
