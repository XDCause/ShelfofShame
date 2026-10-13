# Off the Clock

A self-hosted home for your hobbies, built as a full-stack learning project. Runs entirely in
Docker on your own PC; no accounts or subscriptions.

It's one app with a **core** every hobby shares (Home, Journal, Calendar, hobby **Supplies** and the
**Wishlist**) and a **module per hobby** (Models, Board games, Volleyball), each with its own pages
(`/<module>/<page>`, shown as tabs at the top of the hobby). Wide screens have a sidebar; phones
have five tabs: Home, Journal, Calendar, Supplies (with the wishlist) and Hobbies. More hobbies
(scuba, woodworking, pottery...): see [docs/ROADMAP.md](docs/ROADMAP.md).

- **Home**: a hero banner (the day, a greeting, a line for the day, over a photo of what you've
  been working on) with "Write today's entry"; each hobby's stat tiles; **Recent activity** (one feed
  of what you bought, used, started, finished, logged and wrote, with coloured pills); **Quick
  actions**; the journal's to-dos and latest pages; **Building now** (build-step bars) and **Running
  low** (fill bars from each supply's condition).
- **Look**: light and deep-navy dark themes (Settings > Appearance: System / Light / Dark), a
  sidebar with a daily nudge, and a search box in the top bar (Ctrl+K) for kits, supplies and
  journal pages.
- **Journal**: Notion-style pages (BlockNote editor): type `/` for headings, lists, to-dos, quotes,
  tables and photos; type `@` to mention a model, a supply or another page (a pill that opens it).
  Pages save as you type, have a date, an emoji, tags and a pin; search and tag filters. A model's
  or supply's panel lists the pages that mention it, with "+ Write about it".
- **Calendar**: a month of planned events (one-off, weekly or fortnightly, with "Not on this day" for
  a skipped week) and what happened each day (from the activity feed: kits, supplies, plays,
  volleyball games, journal pages). Tap a day for the detail, "+ Event on this day" or "Write about
  this day". A volleyball event offers **Log the result**. Home shows what's **Coming up**.
- **Board games**: your games (Owned / Wanted / Borrowed / Gone, players, time, rating, box photo)
  and every play (who played, who won, how long). "Played @Catan" in the journal offers "Log a play".
- **Volleyball**: games and training with results (sets won and lost), your gear (condition, photo)
  and video links (YouTube thumbnails), all on the calendar and in Recent activity.
- **Drawing (pen, whiteboard)**: "+ Whiteboard" makes a page that is one endless canvas
  (Excalidraw): pen strokes with pressure, shapes, arrows, text, pictures; pan and zoom. With a pen
  (S Pen on a Galaxy Tab) it switches to pen mode by itself: the pen draws, fingers pan and zoom.
  In a normal page, `/` Drawing adds a sketch: its picture sits in the page, tap it to draw full
  screen. Everything saves by itself; words written on a canvas are searchable.
- **Pen box** ("✍ Pen box" on a journal page): a plain text box at the foot of the page for a
  tablet's handwriting-to-text (Samsung "S Pen to text" only works in plain text boxes, not in the
  rich-text editor). Each finished line moves into the page.
- **Journal -> actions**: write "Just bought @Sherman and started it right away" and the page
  offers "Sherman: Mark as In progress?" (Yes / Not now); "primed @Zero" offers the build step;
  "I want to buy new @XF-10 for a new project" offers "Add to wishlist?".
  Nothing changes without a tap. Check-list items (`/` Check List) on every page form one **To do**
  list, on the Journal page and Home, ticked off without opening the page.

## Shelf of Shame (model kits)

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
- **Hobbies**: scale models, Warhammer and Gundam. Each has its own build steps (Gundam: Built,
  Panel lined, Decals, Top coat), Gundam kits have a grade (HG = 1/144, MG = 1/100...), Warhammer
  boxes have an army and count the minis painted ("3 of 10")
- **Kit lookups**: Tamiya and Hasegawa from their own sites; **Bandai via HobbyLink Japan
  (hlj.com)** by the code on the box (`G5057403`), the box barcode, or a name. Name, grade, scale
  and box photo filled in
- **Colours**: matches between Tamiya ranges (same code, same colour name), your own matches
  between any brands, and mixes ("XF-62 + XF-2 (3:1)") that work on model paint lists
- **Settings**: spending (lifetime / year / month), price guide, default shop, backups (back up
  now, download), CSV export for Excel, Tamiya catalogue refresh, brands / categories / locations
- Styled after Apple's Human Interface Guidelines (sidebar on wide screens, tab bar and sheets on
  phones, dark mode)
- Nightly backups, 221 automated API tests and a 50-step browser walkthrough

Three Docker containers:

| Container | What it is | Address on this PC |
|---|---|---|
| `hobby-inventory-web` | React app (built with Vite), served by nginx; forwards `/api/*` to the API | http://localhost:8080 |
| `hobby-inventory-api` | FastAPI backend, the only thing that talks to the database | http://localhost:8000/api/docs |
| `hobby-inventory-db` | PostgreSQL 17 | `localhost:5433` (DBeaver) |

```
Browser -> web (nginx) -> api (FastAPI) -> db (PostgreSQL)
```

> **Personal tool.** Some data sources and shortcuts are only OK because this runs for one person
> on their own PC. See [BEFORE_GOING_PUBLIC.md](BEFORE_GOING_PUBLIC.md) before sharing, hosting
> or selling it.

## Dev and prod

Two copies of the app run side by side on this PC, so big changes can be tried out before they
touch your real data:

| | **prod** (your real data) | **dev** (test copy) |
|---|---|---|
| Folder | `C:\Users\xdhar\hobby-inventory` | `C:\Users\xdhar\hobby-inventory-dev` |
| Git branch | `main` | `dev` |
| Web app | http://localhost:8080 | http://localhost:8081 (orange **DEV** badge) |
| API | http://localhost:8000/api/docs | http://localhost:8001/api/docs |
| Database | `localhost:5433`, volume `hobby_pgdata` | `localhost:5434`, volume `hobby_dev_pgdata` |

The dev folder is a git *worktree* (a second checkout of the same repository). Changes are made
and committed there, tested there, then moved to prod:

| Task | Command |
|---|---|
| Set up the dev copy (first time) | `.\dev.ps1 -Setup` |
| Rebuild and start dev after code changes | `.\dev.ps1` |
| Give dev a fresh copy of prod's data | `.\dev.ps1 -Refresh` (prod is only read) |
| Stop dev | `.\dev.ps1 -Stop` |
| See which database changes a copy has | `.\migrate.ps1 -List` |
| **Move tested changes to prod** | `.\promote.ps1` in the prod folder (`-Quick` skips the browser walk-through, `-Push` pushes to GitHub) |

`promote.ps1` refuses to run if either copy has uncommitted changes. Then it:
1. runs the API tests and the browser walk-through against dev;
2. backs up prod;
3. fast-forwards `main` to `dev`;
4. applies new `db\init` files with `migrate.ps1` (recorded in the `schema_migrations` table, so
   each runs once);
5. rebuilds prod and waits for it to be healthy.

If anything fails after the backup, it prints the commands to go back.

All the scripts (start, backup, tests, walk-through, migrate) work in either copy: they read
their container names and ports from that copy's `.env`.

See [docs/ROADMAP.md](docs/ROADMAP.md) for where the app is heading (journal, calendar, more hobbies).

## API endpoints

Grouped as in `api/app/` (one module per part of the app):

| Method | Path | Does |
|---|---|---|
| **activity.py** (core) | | |
| GET | `/api/activity?limit=&since=&until=` | What you've done: stock, kits, build log, time, journal, plays, volleyball, gear |
| **journal_drawings.py** (core) | | |
| POST | `/api/journal/{page_id}/drawings` | A new sketch for a Drawing block |
| GET / PUT / DELETE | `/api/journal/drawings/{id}` | A drawing's scene (strokes, shapes) / save it / delete a sketch |
| PUT | `/api/journal/drawings/{id}/files` | Pictures on the canvas (each sent once, merged in) |
| GET / PUT | `/api/journal/drawings/{id}/preview` | Its PNG picture |
| **calendar.py** (core) | | |
| GET | `/api/calendar?start=&end=` | `events` (repeats expanded) and what `happened` each day |
| GET | `/api/calendar/upcoming?limit=` | The next events from today |
| POST / GET / PATCH / DELETE | `/api/calendar/events[/{id}]` | Events; POST `.../{id}/skip {day}` = not on that day |
| **boardgames.py** | | |
| GET / POST | `/api/board-games` | Games; `/summary`, `/plays` (every play) |
| GET / PATCH / DELETE | `/api/board-games/{id}` | One game with its plays; `/photo` GET / PUT / DELETE |
| POST, PATCH / DELETE | `/api/board-games/{id}/plays`, `/api/board-game-plays/{id}` | Plays |
| **volleyball.py** | | |
| GET / POST, GET / PATCH / DELETE | `/api/volleyball/games[/{id}]` | Games and training; `/api/volleyball/summary` |
| GET / POST, GET / PATCH / DELETE | `/api/gear[/{id}]` | Gear; `/photo` GET / PUT / DELETE |
| GET / POST, PATCH / DELETE | `/api/volleyball/videos[/{id}]` | Video links |
| **journal.py** (core) | | |
| GET/POST | `/api/journal?q=&tag=&mention=model:3` | Pages (newest first, pinned on top) / start a page |
| GET/PATCH/DELETE | `/api/journal/{id}` | One page with its blocks, tags, mentions and "mentioned in" |
| GET | `/api/journal/tags`, `/api/journal/mentionable?q=` | Tags in use / what `@` can mention |
| GET · PATCH | `/api/journal/todos?done=` · `/api/journal/{id}/todos/{block}` | Check-list items from every page / tick one `{"checked": true}` |
| POST | `/api/journal/{id}/suggestions/apply`, `.../dismiss` | Do (or wave away) a suggestion `{"key": ...}` |
| POST | `/api/journal/images` · GET `/api/journal/images/{id}` | A photo in a page (image as the body) |
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
| GET | `/api/lookup/bandai/{code}` | Bandai kit from hlj.com by box code (`G5057403`), barcode, HLJ code or name (`{"choices": [...]}` if several match) |
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
| GET/PATCH/DELETE | `/api/models/{id}` | One kit with its checklist, sessions and build log; `hobby`, `stage`, `grade`, `faction`, `figures` / `figures_done`, `brand_name` (a new brand) |
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
| Apply new database changes (`db\init` files not yet applied) | `.\migrate.ps1` |
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
