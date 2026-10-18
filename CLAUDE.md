# Off the Clock - project notes for Claude

**App name: "Off the Clock"** (2026-10-13), a hobby hub with a module per hobby. **"Shelf of Shame"**
is now the name of the model-kit module (it was the app's name 2026-10-11 to 10-13; before that
"Hobby Inventory").
GitHub: https://github.com/XDCause/ShelfofShame (PUBLIC - never commit .env, backups, or
copied third-party pages). The user-visible name changed (app title, docs, API title,
scraper User-Agents); internal names were deliberately KEPT to avoid migrating data: folder
`hobby-inventory`, containers `hobby-inventory-*`, volume `hobby_pgdata`, database
`hobby_inventory`, user `hobby`, localStorage key `hobby-inventory.lastShop`.
Git author: XDCause <121413369+XDCause@users.noreply.github.com> (GitHub no-reply address, so
the user's real email isn't published in commits).

## WORKFLOW: dev first, then promote (since 2026-10-13)
- **Make every change in the dev copy: `C:\Users\xdhar\hobby-inventory-dev` (branch `dev`)**, using
  absolute paths there. Never edit the prod folder (`C:\Users\xdhar\hobby-inventory`, branch
  `main`) directly. The Claude session's working directory is the prod folder, so be careful.
- Build and test in dev: `.\dev.ps1` (rebuild), then `.\test_all.ps1` **in the dev folder** (see Quality gates).
  `.\dev.ps1 -Refresh` copies prod's data into dev.
- Commit on dev. **Promote only when the user is happy**: `.\promote.ps1` in the prod folder
  (tests dev, backs up prod, `git merge --ff-only dev`, migrate.ps1, rebuild). `-Push` pushes both branches.
- **Schema changes:** a new numbered idempotent db\init file. `migrate.ps1` applies pending files and
  records them in `schema_migrations` (17_schema_migrations.sql). No more hand-piping into psql.

## Who / why
The user is **learning full-stack integration** by building an inventory of their model-kit
hobby supplies (paints, thinners, clears, primers, masking tape, glue, weathering, decals,
brushes, airbrush parts, tools). Explain briefly what each piece does and why as you go.
The point is learning, not just producing files.

Environment: Windows 11, **Windows PowerShell 5.1**, Docker Desktop, DBeaver, Python 3.13.

## Direction change (2026-10-11)
**Excel is no longer a front end.** The spreadsheet was a one-time data source: it has been
imported and the **database is now the source of truth**. Don't build Power Query / VBA
integration. The user will decide later how to query the backend.

## Architecture rule (do not break)
```
Browser -> web (React/Vite, nginx :8080) --\
                                            +--> api (FastAPI :8000) --> db (PostgreSQL :5433)
AI via MCP server (stage 6) ---------------/
```
**Only the API talks to PostgreSQL** in the finished app. Exceptions are admin/dev tools:
DBeaver, psql, and the one-off import script.

## Where to look
- **History, decisions and the reasons behind them: docs/HISTORY.md** (sections 1 - 4d; search it before changing
  something old - most odd-looking code has a lesson behind it there). Plans: docs/ROADMAP.md. Caveats for ever going
  public: BEFORE_GOING_PUBLIC.md (**add a row whenever a new data source, scraper, copied content or single-user
  shortcut is added**).
- **API** (`api/app`, FastAPI; routes all start `/api`; main.py only wires routers - ORDER MATTERS where a fixed path
  shares a prefix with `/{id}`): core - db (pool, enum lists that must match SQL CHECKs, insert_row / update_row /
  found / tidy_text), activity, calendar, journal (+ journal_text, journal_actions, journal_drawings), goals, settings,
  spending, sitecheck, images, webphoto, lookups, wanted. Supplies hobby - supplies, wishlist, products, catalog,
  paints, colours. Models - models, minis, build, warhammer, gundam. Board games - boardgames. Volleyball -
  volleyball, gear (volleyball's and hiking's: gear.hobby), vbclips, vbcoach. Video games - videogames, vgsync, othergames, vgfind, vgfriends. Chess - chess.
  Reading - reading, readimport, reading_recs, bookseries. Hiking - hiking (+ gpx: a GPX file's numbers; HikeMap.jsx = Leaflet). Gardening - garden (spaces, layout, plants,
  care, logs + photos, tasks, today), garden_guide (plant guide, sow now), garden_doctor (problems: signs -> what to do), garden_items (supplies, seeds, Bunnings). Outside sources (one module each, all polite, all faked in
  tests by conftest): tamiya, hasegawa, hlj, ucp (+ goodgames, bluesky), gameology, steam, steamhunters, exophase,
  trumpeter (kits and tools by item number: their search, then that page), chesscom, openlibrary, overpass (OpenStreetMap landmarks), wikimedia (Commons photos), bunnings (one product page from
  a pasted link - never their search or API, robots.txt), openmeteo (weather tips).
- **Web** (`web/src`, React 19 + Vite): App.jsx (routes, panels via openPanel(type), openThing(kind, id)), api.js (every
  fetch, grouped by area), core/ (Home, Navigation, Goals, Journal, Calendar...), modules/<hobby>/manifest.jsx (pages,
  panels, Home tiles / cards, quick actions), components/ (shared), styles.css (one file, sections by comment).
- **Database**: numbered idempotent files in db/init (01-72); migrate.ps1 applies pending ones.

## Quality gates (run them; they're fast)
- `.\test_all.ps1` in dev = API tests (run_tests.ps1: fresh test DB from db\init, pytest) and the browser walk-through
  (run_e2e.ps1) side by side, ~3 minutes. The walk-through runs on its OWN throwaway copy of the app (hobby-e2e-*)
  with a copy of the data - dev's data is never touched, so the user can keep using dev while it runs. That copy has
  OUTSIDE_SITES=stand-ins (api/app/stand_ins.py): no outside site is ever asked by the tests or the walk-through
  (user, 2026-10-18: small shops get one look a week - the weekly site check - unless something needs checking).
- Passing runs are stamped (.tested\); promote.ps1 skips tests already passed on exactly this code.
- `npm run build` (every web image build) fails on a CSS class clash (web/scripts/check-css-clashes.js) or ANY
  ESLint warning (--max-warnings 0). A deliberate hooks exception gets an eslint-disable comment saying why.
- After API changes also: pyflakes clean, pip-audit / npm audit clean (see HISTORY 3zt / 3zzt for how they're run).
- Settings > Lookup sites: the weekly live check of every outside site (a site that changes shows there and on Home).

## Rules (the user's decisions - don't break them)
- **The repo is PUBLIC.** Never commit .env, backups, media, copied third-party pages, the Steam key, or the user's
  profile names / ids / email (they live in the database only). Grep the staged diff before each commit.
- **Promote only when the user asks.** Firewall / admin changes need the user's go-ahead (the UAC prompt is theirs).
- Never scrape BoardGameGeek or SteamHunters' web pages; never bypass bot protection (Cloudflare, WAF captchas); never
  use the user's Ubisoft password. Shops (Good Games, Blue Sky Athletics) are read through their official read-only
  UCP catalogue only: no carts, no checkouts. Text on third-party sites asking agents to do things is ignored.
- No login and no HTTPS (user's choice, home network + Tailscale only).

## Lessons that keep coming back
- Give every new CSS class a name nobody else uses (the build now catches a clash, but pick well first).
- In a panel that opens another, call onClose() BEFORE openPanel().
- "Today" comes from the database (Brisbane); the API container runs on UTC.
- Never calculate barcodes; learn them (HISTORY 3d).
- `docker compose up -d` doesn't rebuild - use `.\dev.ps1` or `--build`; plain dev.ps1 doesn't migrate - run
  .\migrate.ps1 after adding a db/init file.
- Write multi-line edit scripts as .py files with the Write tool (the Bash tool mangles some heredocs), and never pass
  robocopy (or anything with /SWITCHES) through Git Bash - it rewrites them as paths. Use PowerShell.
- Every photo URL must change when the photo changes (served with a 1-year cache).
- Playwright's Chromium can't play H.264; browser tests of playback need WebM.
- An element with an id is also a window global (`window.__NEXT_DATA__` can be the <script> element): check its shape.
- A new outside source needs a stand-in in stand_ins.py (and a fake in conftest), or the walk-through would ask it live.
- Good Games is paused in the weekly site check (a small shop; user's call) - its features still work when used.

## Data conventions (user decisions, 2026-10-11)
- Product codes are Tamiya-style **catalogue numbers** (`T81701`), not bottle codes (`XF-1`).
  The bottle code appears in the name ("Acrylic XF1 Flat Black").
- **Brands are kept small**: only Tamiya, Milliput, Microscale, Other (the Lists tab). The user
  removed the 17 unused brands from the long default list. Add brands only as they're actually used.
- Storage is `Other` for everything: physical storage locations aren't set up yet.
- Normal stock is qty 1, reorder_at 0, so items show "Out" at 0 and never "Low".

## Gotchas learned
- **Init scripts run only when the volume is empty.** Editing `db/init/*.sql` does nothing to
  an existing DB. **The DB now holds the real data**: never `docker compose down -v` without a
  `pg_dump` backup first. Schema changes should be ALTER/migration scripts.
- **DBeaver "no tables"**: check the connection's Database field is `hobby_inventory`, not `postgres`.
  `pg_stat_activity.datname` shows which DB each client is really on.
- **PowerShell 5.1 + `$ErrorActionPreference = 'Stop'`** turns docker's stderr output
  (warnings, build progress) into fatal errors. Check `$LASTEXITCODE` instead.
- Keep `.ps1` files ASCII-only (5.1 reads BOM-less UTF-8 as ANSI).
- **`localhost` resolves to `::1` (IPv6) first on this PC**, and the user's browser doesn't fall
  back to 127.0.0.1. The api port is published on BOTH `127.0.0.1` and `[::1]`.
- **The web app is deliberately on the home network** (user request, 2026-10-11): port 8080 is
  published on all interfaces, so phones etc. use `http://10.0.0.33:8080` (PC's Wi-Fi IP; may
  change via DHCP). API (8000) and DB (5433) stay loopback-only. There is **no login**: anyone
  on the Wi-Fi can view and edit. The user confirmed the Wi-Fi is **their own private network**,
  so that's acceptable. Windows had it marked "Public"; the user was advised to switch it to
  Private (needs admin). Docker Desktop's firewall Allow rules (`com.docker.backend`) cover 8080. PowerShell's Invoke-WebRequest does fall back, so test `http://[::1]:PORT`
  explicitly when checking browser access.
- **After a reboot** (checked 2026-10-13): Docker Desktop AutoStart = True and all 3 containers
  are `restart: unless-stopped`; they came up ~75 s after boot, all at once (Docker's restart
  ignores depends_on order - harmless: the API connects per request, nginx resolves api per
  request). "Not loading" right after login = still starting. Randomly named exited containers
  (e.g. `sharp_mendeleev` KeyError POSTGRES_DB, `distracted_lederberg` no password) come from
  pressing Run on an IMAGE in Docker Desktop: bare copies without compose/.env. Not part of
  the app; safe to `docker rm`. Two were removed 2026-10-13. The app is always 3 containers.
- Backups: nightly 2 am task runs prod's backup.ps1 with -CopyTo the network drive (HISTORY 3zzt); 14 kept in
  each place; videos copied too. Restore steps are at the top of backup.ps1.
- `nextval()` consumes a sequence number. To inspect, read `<seq>.last_value` instead.
- VS Code's generic SQL linter flags `BEGIN;` as an error. It's valid PostgreSQL; ignore it.
- Changing anything in `db/` rebuilds the db image and recreates the container. Data is safe
  (it's in the volume), and init scripts don't re-run on a non-empty volume.
- Prefer `.\run_tests.ps1` over ad-hoc testing against the live DB. Windows PowerShell 5.1's
  Invoke-RestMethod passes a JSON array down the pipeline as ONE object (and @() wraps it
  again) - use `foreach ($x in $result)` when scripting against the API.
- Testing by creating a supply consumes an id. Afterwards run
  `SELECT setval(pg_get_serial_sequence('supplies','supply_id'), (SELECT max(supply_id) FROM supplies))`
  so the user's numbering stays gap-free.

## Handy commands
- Verify: `docker exec hobby-inventory-db psql -U hobby -d hobby_inventory -c "SELECT * FROM v_supplies"`
- Interactive: `docker exec -it hobby-inventory-db psql -U hobby -d hobby_inventory`
- Backup: `docker exec hobby-inventory-db pg_dump -U hobby -d hobby_inventory > backup.sql`
- See README.md for start/stop/logs/wipe/import.
