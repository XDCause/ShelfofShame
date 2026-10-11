# Shelf of Shame

A self-hosted inventory for model-kit supplies (paints, thinners, tape, glue, tools...), built
as a full-stack learning project. Runs entirely in Docker on your own PC; no accounts or
subscriptions.

- **Inventory**: search, filter, sort, photos, +/- stock, per-item stock history
- **Wishlist**: phone-friendly shopping list; tick things off in the shop, then move them into
  inventory in one go
- **Barcode scanning** from a phone photo (decoded in the browser), with a built-in catalogue
  of Tamiya Acrylic Mini paint barcodes
- **Tamiya lookup**: type an item number or paint code (e.g. `XF-76`) to fill in the name,
  photo, size, paint type and finish from tamiya.com
- Nightly backups and an automated API test suite

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

| Method | Path | Does |
|---|---|---|
| GET | `/api/supplies?q=&category=&brand=&status=&location=` | Search / filter |
| GET | `/api/supplies/low-stock` | Everything Low or Out |
| GET | `/api/supplies/{id}` | One supply |
| POST | `/api/supplies` | Add a supply |
| PATCH | `/api/supplies/{id}` | Change some fields |
| POST | `/api/supplies/{id}/adjust` | `{"delta": -1}` = used one, `{"delta": 2}` = bought two |
| DELETE | `/api/supplies/{id}` | Delete a supply |
| GET | `/api/wishlist?show=all\|needed\|got` | Wishlist, with photos and "you own N" |
| POST | `/api/wishlist` | Add a wishlist item |
| PATCH | `/api/wishlist/{id}` | Edit; `{"got_it": true}` ticks it off |
| DELETE | `/api/wishlist/{id}` | Remove from wishlist |
| POST | `/api/wishlist/{id}/buy` | Bought it: move to inventory `{"purchased_from": "..."}` |
| POST | `/api/wishlist/buy-ticked` | Move every ticked item to inventory |
| GET | `/api/lookup/tamiya/{item}` | Product details + photo from tamiya.com (cached after first time) |
| GET | `/api/scan/{barcode}` | Identify an item from its barcode number (known / catalog / Tamiya / unknown) |
| GET | `/api/supplies/{id}/history` | Quantity changes for one supply, newest first |
| GET | `/api/history` | Quantity changes across everything |
| POST | `/api/wishlist/restock` | Put everything that needs attention (Out or Low) on the wishlist |
| PUT | `/api/product-barcode` | Remember a barcode `{"brand_id", "product_code", "barcode"}` |
| GET | `/api/product-images/{id}` | A cached product photo |
| PUT | `/api/product-photo?brand_id=&product_code=` | Your own photo for any item (image file as the body) |
| DELETE | `/api/product-photo?brand_id=&product_code=` | Remove an item's photo |
| GET | `/api/lookups` | Brands, categories, locations (with usage counts) + fixed choice lists |
| POST | `/api/lookups/{brands\|categories\|locations}` | Add a list entry `{"name": "..."}` |
| DELETE | `/api/lookups/{kind}/{id}` | Remove an unused list entry |

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
| Back up now (also runs nightly at 2 am) | `.\backup.ps1` (keeps the newest 14 in `backups\`) |
| Back up and copy elsewhere | `.\backup.ps1 -CopyTo "D:\Backups"` |
| Run the automated tests (never touches real data) | `.\run_tests.ps1` (or `.\run_tests.ps1 -k wishlist`) |

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
