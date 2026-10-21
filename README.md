# Off the Clock

A self-hosted home for your hobbies, built as a full-stack learning project. Runs entirely in
Docker on your own PC: one account (yours), no subscriptions, nothing in the cloud.

It's one app with a **core** every hobby shares and a **module per hobby**, each with its own pages
(`/<module>/<page>`, shown as tabs on the hobby's banner). Wide screens have a sidebar; phones have
five tabs: Home, Journal, Calendar, Supplies (with the wishlist) and Hobbies. Ideas for later: see
[docs/ROADMAP.md](docs/ROADMAP.md).

## The core

- **Home**: the day and a greeting over a photo of what you've been doing, each hobby's numbers,
  **Recent activity** (one feed of everything you bought, used, played, logged and wrote), quick
  actions, what's coming up, to-dos and goals that need a nudge.
- **Goals**: big-picture goals for a year or three, with why they matter, a plan, steps (to-dos) and
  progress - counted by hand or by the app itself (books finished, km hiked, a chess rating...).
  Habits, yes / no goals, goals inside bigger ones, and whether you're on track. A **To-do** list
  you can put in your own order.
- **Journal**: Notion-style pages (type `/` for blocks, `@` to mention a kit, a game, a book...),
  mood and mood words, tags, notebooks, templates, a weekly / monthly review, a prompt for a blank
  page, place and weather, private pages, lined / grid / dot paper, whiteboards and sketches
  (Excalidraw, pen pressure, S Pen), "On this day", and Calendar, Map and Insights views. Print or
  save as PDF. What you write can offer to update things ("primed @Zero" offers the build step).
- **Calendar**: Month, Week, Agenda and Year views. Events that repeat (weekly, every N weeks, chosen
  weekdays, monthly, "the 2nd Saturday", yearly), quick add in plain words ("Volleyball Tue 7-9pm at
  Sports hall weekly"), countdowns, checklists of what to bring, weather on upcoming events,
  Queensland public holidays, dated to-dos and goals, drag to move, and what actually happened each
  day.
- **Supplies**: everything you own for every hobby - pick a hobby, then its kinds (Models: paints,
  weathering, glue...; Volleyball and Hiking: gear; Shooting: rifles and ammo; Gardening: supplies
  and seeds). Barcode scanning, Tamiya lookups, +/- with Undo and stock history, shelf life once
  opened, colour swatches, set aside for a build, warranties, receipts and manuals. Tools: **places**
  that nest (rack > drawer > box) with printable **QR labels**, **shopping mode**, **stocktake** and a
  **value report** for insurance.
- **Wishlist**: everything you want, from every hobby, by shop or by hobby. Tick it when you buy it
  (with Undo and a history of what you paid), what it's for, a target price, saving up, prices seen,
  "check the shop now" (Blue Sky, Good Games), add from a shop link, and a gift list to share.
- **Look**: light and dark themes, a drawn landscape banner per page (or your own photo), search
  everything with Ctrl+K.

## The hobbies

| Hobby | What it does |
|---|---|
| **Models** (Shelf of Shame) | Scale models, Gundam and Warhammer: the stash and its cost, build steps, a paint checklist (ticked for paints you own), Tamiya / Hasegawa / Bandai (HLJ) / Trumpeter lookups, colour matches and mixes, a build timer and a build log with photos |
| **Board games** | Your games and every play (who played, who won, how long); "Played @Catan" in the journal offers to log it |
| **Volleyball** | Games and training with results, videos and clips, coaching notes, gear |
| **Video games** | Steam achievements and 100% runs (official Steam Web API), other platforms, friends |
| **Chess** | chess.com ratings, games and openings; games over the board |
| **Reading** | Books, a reading log, series, recommendations (Open Library) |
| **Travel** | Trips: bookings, plans, budget, packing lists, places and memories |
| **Precision shooting** | Rifles, ammo, range sessions, groups, each shot, and your DOPE |
| **Hiking** | Hikes from GPX files: distance, climb, routes on a map, splits |
| **Gardening** | A balcony / windowsill garden: layout, plants, watering, photos, harvests, a plant guide and doctor |
| *Building my car* | Under construction - shows in the dev copy only |

Behind it: nightly backups (also copied to the network drive), hundreds of automated API tests, and
a browser walk-through of every page that ends with an accessibility and layout audit at five
screen sizes in both themes.

Three Docker containers:

| Container | What it is | Address on this PC |
|---|---|---|
| `hobby-inventory-web` | React app (built with Vite), served by nginx over HTTPS; forwards `/api/*` to the API | https://&lt;pc&gt;.local:8443 (http 8080 redirects) |
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
| Web app | https://&lt;pc&gt;.local:8443 | https://&lt;pc&gt;.local:8444 (orange **DEV** badge) |
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

## The API

Every route starts with `/api` and needs you signed in. The full, always-current list - every
route, what it takes and what it answers - is the API's own page: **http://localhost:8000/api/docs**
("Try it out" runs one; sign in to the app in the same browser first). The code is in `api/app/`,
one module per part of the app:

| Area | Modules |
|---|---|
| Core | `activity`, `goals` (+ `goal_sources`), `todos`, `journal` (+ `journal_text`, `journal_actions`, `journal_drawings`, `journal_more`), `calendar` (+ `calendar_more`, `holidays`), `banners`, `images`, `webphoto`, `settings`, `system` (Settings > System), `spending`, `sitecheck`, `auth` (+ `auth_passkeys`); `main` wires them up, `db` is the shared database helpers |
| Supplies and wishlist | `supplies` (+ `supplies_more`, `owned`), `wishlist`, `wanted` (+ `wanted_more`, `linkpeek`), `products`, `catalog` (+ `tamiya_catalog`, `catalog_import`), `paints`, `colours`, `lookups` |
| Hobbies | `models`, `minis`, `build`, `warhammer`, `gundam`; `boardgames`; `volleyball`, `gear`, `vbclips`, `vbcoach`; `videogames` (+ `videogames_stats`), `vgsync`, `vgplaytime`, `othergames`, `vgfind`, `vgfriends`; `chess`; `reading`, `readimport`, `reading_recs`, `bookseries`; `travel`, `travel_trip`, `travel_places`; `shooting`, `shooting_sessions`, `shooting_shots`, `shotmath`; `hiking`, `gpx`; `garden` (+ `garden_logs`, `garden_today`), `garden_guide`, `garden_doctor`, `garden_items` |
| Outside sites (one each, polite, faked in tests) | `tamiya`, `hasegawa`, `hlj`, `trumpeter`, `stedi`, `ucp` (+ `goodgames`, `bluesky`), `gameology`, `steam`, `steamhunters`, `exophase`, `chesscom`, `openlibrary`, `overpass`, `wikimedia`, `bunnings`, `openmeteo`, `frankfurter` (exchange rates); `stand_ins` answers for all of them in the walk-through |

The web app's side is `web/src/api.js` (every call it makes, grouped the same way); a test checks
that each of its calls is a real route.

## Signing in and HTTPS

The app asks you to sign in (one account: yours) and is served over HTTPS with its own certificate. It's still only
reachable on the home network and Tailscale - **never forward a port to it on the router, or turn on Tailscale Funnel**.

**Set the password (on this PC, in the app's folder):** `.\set-password.ps1`. There's no sign-up page on purpose, so
nobody else on the Wi-Fi can get there first. Then open the app and sign in.

- Settings > Security: change the password, set up an **authenticator app** (6-digit codes; you get 10 recovery codes -
  keep them safe), add **passkeys** (Face ID / fingerprint / PIN), see and sign out **devices** (each stays signed in
  30 days).
- **Lost your phone or password?** On the PC: `.\set-password.ps1 -ResetAuthenticator -SignOutEverywhere`.
- Five wrong passwords or codes from one device (or twenty from anywhere) in 15 minutes and signing in waits 15 minutes.

**HTTPS on your devices (once each).** `.\make-cert.ps1` makes "Off the Clock local CA" the first time (kept in
`%USERPROFILE%\.offtheclock\ca`, shared by dev and prod; never in the repo) and this copy's certificate (`certs\`,
git-ignored). Install the CA once on every device you use - then there are no warnings, and passkeys work:

- **This PC (Windows):** double-click `certs\offtheclock-ca.crt` > Install Certificate > Current User > *Place all
  certificates in the following store* > **Trusted Root Certification Authorities** > Finish (Windows asks you to confirm).
- **iPhone / iPad:** in Safari open `http://<PC's IP>:8080/ca.crt` > Allow; Settings > *Profile Downloaded* > Install;
  then Settings > General > About > **Certificate Trust Settings** > turn on "Off the Clock local CA".
- **Android:** open `http://<PC's IP>:8080/ca.crt` to download it; Settings > Security > Encryption & credentials >
  **Install a certificate** > CA certificate > pick it.

Then use **https://&lt;pc&gt;.local:8443** (the PC's name, e.g. travel-laptop.local) - passkeys need the name; an IP address
(https://10.0.0.33:8443) works for everything else. Over Tailscale: https://&lt;pc&gt;.&lt;tailnet&gt;.ts.net:8443. The
certificate covers all of these; `.\make-cert.ps1` remakes it if the PC's names or addresses change (dev.ps1,
start.ps1 and promote.ps1 run it).

## First-time setup

1. Install and start Docker Desktop.
2. Copy `.env.example` to `.env` and set `POSTGRES_PASSWORD`.
3. Run `.\start.ps1` (it makes the HTTPS certificate on the first run), then `.\set-password.ps1` to set your sign-in
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
| Test-restore the newest backup now (it also happens weekly by itself) | `.\backup.ps1 -TestRestore` |
| **Encrypted copy to Google Drive** (once; prod folder) | install Google Drive for desktop, then `.\setup-offsite.ps1` |
| Get a Google Drive copy back | `.\restore-offsite.ps1 -File "G:\My Drive\Off the Clock backups\<file>.dump.gpg"` |
| How it's all doing (backups, syncs, disk, updates) | Settings > System (Home shows anything that needs a look) |
| Check for updates (monthly; dev folder) | `.\check-updates.ps1` |
| **Run every check** (API tests + web tests + walk-through + audit, side by side, ~9 min; in dev) | `.\test_all.ps1` |
| Run the web code's own tests (about a minute) | `.\run_web_tests.ps1` |
| Run the automated API tests (never touches real data) | `.\run_tests.ps1` (`-k wishlist` for some; `-Coverage` shows untested lines) |
| Click through the whole app in a browser (desktop + iPhone) | `.\run_e2e.ps1` (on its own throwaway copy of the app and data - yours is never touched; screenshots in `e2e\out\`) |

## Restoring a backup

Replaces the current data with the backup's:

```powershell
docker cp .\backups\hobby_inventory_YYYYMMDD_HHMMSS.dump hobby-inventory-db:/tmp/restore.dump
docker exec hobby-inventory-db pg_restore -U hobby -d hobby_inventory --clean --if-exists /tmp/restore.dump
```

The nightly backup is the Windows scheduled task **"Shelf of Shame backup"** (Task Scheduler). Each backup is read
back to check it, and once a week one is restored for real into a throwaway database and every table's rows
compared; results are in `backups\backup.log` and Settings > System. The encrypted Google Drive copies keep the last
7 days, one a week for 4 weeks and one a month for 6 months (about 200 MB; videos stay on the network drive).

Useful psql commands: `\dt` list tables, `\dv` list views, `\d supplies` describe a table, `\q` quit.

## Changing the database

`db/init/*.sql` builds a new, empty database the first time it starts. After that, a change is a
**new numbered file** in `db/init` that's safe to run twice (`IF NOT EXISTS`, guarded constraints);
`.\migrate.ps1` applies the files a copy hasn't had yet and records each in `schema_migrations`
(`promote.ps1` runs it for prod). Editing an old file does nothing to an existing database. Never
`docker compose down -v` (it deletes the data) without a backup first.

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
