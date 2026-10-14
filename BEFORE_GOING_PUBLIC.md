# Before going public or commercial

Shelf of Shame is a **personal, single-user tool**: it runs on one PC, for one person, and only
reads other websites when that person asks it to. Several shortcuts are fine on that basis but
**would not be fine** in an app that other people use, that is hosted for others, or that makes
money. This file lists them, so they can be dealt with before that happens.

Keep it up to date: **whenever a new data source, scraper or shortcut is added, add it here.**

> Not legal advice. "Fine for personal use" here means low-risk and in line with each site's
> robots.txt, not that anyone has granted permission. Before going commercial, get the
> permissions below in writing and have the terms checked properly.

Status key: **OK** = fine as is · **Change** = must change before going public/commercial ·
**Check** = probably fine, confirm first.

---

## 1. Data taken from other websites

The biggest item. All of these are fetched **one item at a time, only when you ask**, with a
pause between requests and an honest User-Agent saying it's a personal tool. They're cached in
your own database, never in the repo. A public or commercial app changes all of that: many
users means many requests, and showing their photos to the public is republishing them.

| Source | What we take | Where in the code | Personal use | Public / commercial |
|---|---|---|---|---|
| **tamiya.com** product pages | Title, description, **product photo**, size/type hints | `api/app/tamiya.py`, `products.py` | No robots.txt; the user understood Tamiya allows it. | **Change.** Photos and description text are Tamiya's copyright. Get permission (or an official feed / affiliate deal), or keep only facts (name, code, size) and link to Tamiya's page. |
| **YouTube** video thumbnails (volleyball videos) | The thumbnail image for a YouTube link, **hot-linked** from img.youtube.com | `VolleyballViews.jsx` | Your own links, shown to you. | **Check.** Embedding / showing thumbnails is allowed under YouTube's terms in an app that links to the video, but use the official embed or API and follow their branding rules. |
| **esm.sh** (drawing canvas fonts, backup only) | Fonts are served by the app; Excalidraw lists esm.sh as a backup source, allowed in the content security policy | `web/security-headers.inc`, `public/excalidraw-assets.js` | Never used while our copies exist. | **Fine**, or drop esm.sh from `font-src` and accept a console warning. Excalidraw itself is MIT licensed. |
| **Steam Web API** (Video games) | Your games, playtime, achievements, achievement names / icons / rarity; **game and achievement pictures hot-linked** from Steam's CDN | `api/app/steam.py`, `videogames.py`, `modules/videogames` | Official API with your own key (in `.env`, never committed); ~3 calls per game on the first sync, then only played games; 100,000 calls/day allowed. | **Check.** The Steam Web API Terms of Use allow apps built on it, but each user needs their own key or you need Valve's terms for a shared one; game art belongs to Valve and the publishers (link to it, don't copy it). Never ship a key in the app. |
| **SteamHunters API** (Video games: median / fastest time to 100%, how many players 100%'d a game) | Numbers per game from `steamhunters.com/api/apps/<id>` (their public JSON API, used by their open-source browser extension) | `api/app/steamhunters.py`, `videogames.sync_community` | Only the user's started games, 1 request/second, saved; re-read only during a sync (played since / weekly / full). Their web pages are behind a bot check and no API terms are published. | **Ask first.** No published terms or limits; the data is SteamHunters' own (from their users). Get permission (or use their official route, if one exists) before any public use. |
| **Exophase** (Video games: which achievements come with a DLC) | Each game's achievement page on `www.exophase.com/game/<slug>-steam/achievements/` (DLC sections), found with their site's public search API `api.exophase.com/public/archive/games?q=` | `api/app/exophase.py`, `videogames.sync_dlc` | Only started games with DLC, one request every 2 s; saves only which DLC each achievement belongs to (names, no text or pictures); read once, again when a game's achievements change or on a full sync. robots.txt only blocks /search; their terms say nothing about automated access; no API terms are published. | **Ask first.** The grouping is Exophase's work. Get permission (or an official API) before any public use. |
| **Exophase profile** (Video games: Epic achievements, Ubisoft names / pictures / playtime) | The user's own public profile page (player id per platform) and `api.exophase.com/public/player/<id>/games?environment=epic|uplay` (the JSON their site uses) | `api/app/exophase.py` (profile_players, player_games), `api/app/othergames.py` | One user's own profile; 1 page + 1-2 requests per platform per sync, spaced 2 s. robots.txt only blocks /search; no API terms published. | **Ask first** - and a public version would need each user's consent to read their profile. Ubisoft achievements are typed in by the user (Exophase only sees Ubisoft *challenges*). |
| **Steam store search** (Video games: finding an Epic / Ubisoft game's Steam version) | `store.steampowered.com/api/storesearch/?term=` - the JSON Steam's own store uses (not part of the documented Web API) | `api/app/steam.py` find_app | Once per Epic / Ubisoft game (a few words dropped at most), spaced; the result is saved. | Fine for personal use; at scale use the official IStoreService/GetAppList instead. Ubisoft achievement lists come from the Steam version's schema (official API), assuming the PC lists match (they did for Siege: 48 = 48). |
| **chess.com public API** (Chess: profile, ratings, every game) | `api.chess.com/pub/player/<user>/...` - chess.com's official, documented read-only API | `api/app/chesscom.py`, `api/app/chess.py` | One account; one request at a time; past months read once. | Fine - it's published for this. At scale follow their rate guidance (serial requests, a User-Agent with contact details). |
| **Open Library** (Reading: book search, ISBN lookup, covers) | `openlibrary.org/search.json` (their documented API; robots.txt only keeps crawlers off the HTML `/search` pages) and covers shown straight from `covers.openlibrary.org/b/id/<id>-M.jpg` | `api/app/openlibrary.py`, `api/app/reading.py` | One user; lookups when adding a book; after a Goodreads import one request a second, by cover id (not ISBN) for images. User-Agent names the app and its repo. | Open data (Internet Archive). At scale: ask them, send a contact address in the User-Agent, cache covers instead of hot-linking (their cover API limits non-id lookups to 100 per 5 minutes per IP). |
| **Goodreads export** (Reading: import) | The user's own "Export library" CSV, uploaded by them | `api/app/reading.py` (`goodreads_rows`) | Their own data, read once per upload; nothing is fetched from Goodreads. | Fine. (Goodreads has no public API any more - never scrape it.) |
| **Gameology** (Board games: find a game, fill in BGG's players / time / age / weight / categories / mechanisms, box photo, price) | An Australian shop's Shopify storefront: `/search/suggest.json` (its own search box) and `/products/<handle>.js`; photos from cdn.shopify.com | `api/app/gameology.py`, `api/app/boardgames.py` | One user; a search as you type a name, one product + one photo per game added; User-Agent names the app and its repo. robots.txt allows product pages. Photos are copied into the database. | Their agents.md asks automated server-to-server traffic to identify itself with Shopify's Web Bot Auth (signed requests) - this app only sends a User-Agent. A public app should ask Gameology first (and use their catalogue properly), or use BGG's registered API. Product photos and the BGG-derived facts aren't ours to republish. |
| **Video uploads** (Volleyball videos) | Your own files, uploaded from your phone / PC | `api/app/volleyball.py` (`upload_video`), `web/nginx.conf` (4 GB for that one address), `docker-compose.yml` (`./media` -> `/media`) | Files are kept in the `media` folder next to the app, NOT in the database; backup.ps1 (the nightly task) copies new ones to `backups\media` (never deleting, so a mistaken delete can be undone) - the app's own "Back up now" button covers the database only. No login: anyone on the Wi-Fi can upload up to 4 GB each. | A public app needs logins, per-user storage limits, virus / type checks beyond the file's first bytes, and its own backups (or object storage) for media. |
| **BoardGameGeek** links | Only a link you paste; the app never fetches BGG | `GamePanel.jsx` | Fine. | **Fine** as a link. A lookup (names, photos) would need BGG's XML API, which requires registration and has its own terms. |
| **tamiya.com** kit pages | "Colors required" paint list | `tamiya.parse_kit_paints` | As above. | **Check.** A paint list is mostly facts; ask anyway when asking about photos. |
| **tamiya.com** product list ("Shop Tamiya") | ~1,000 titles + item numbers; **thumbnails hot-linked** from Tamiya's CDN | `api/app/tamiya_catalog.py`, `CatalogSearch.jsx` | One-off import you run by hand; 2 s between pages. | **Change.** Hot-linking shows Tamiya's images on our pages and uses their bandwidth. A copy of their whole catalogue is a database built from their site. Needs permission. |
| **hasegawa-model.co.jp** kit pages | Name, scale, item number, **box photo** | `api/app/hasegawa.py` | robots.txt only blocks their admin area; no terms page found. | **Change.** Box art is copyright. Ask Hasegawa, or link instead of copying the photo. |
| **hlj.com** (HobbyLink Japan) for Bandai kits | Name, grade, scale, barcode, series, **box photo**; search results with **hot-linked thumbnails** | `api/app/hlj.py`, `products.lookup_bandai`, `ModelForm.jsx` | robots.txt allows product and search pages. The user chose to keep photos ("internal tool just for me"). | **Change.** HLJ's [Copyright page](https://support.hlj.com/hc/en-us/articles/201079650-Copyright) says text and images belong to HLJ or its suppliers and warns against unauthorised copying or commercial use. Their [Terms](https://support.hlj.com/hc/en-us/articles/115001722094-Terms-Conditions-of-Use) also say accounts using bots to manipulate the site can be closed. Needs HLJ's permission (or an affiliate/data agreement), or facts only plus a link. |
| **rchobbyland.com.au** | Barcode → Tamiya item number for ~100 Acrylic Mini paints (the barcode catalogue) | `api/app/catalog_import.py` | One-off import you run by hand. robots.txt allows product pages (Crawl-delay 1; we use 2 s). We store only barcode → item facts. | **Change.** Their terms prohibit reproducing their content. A barcode list built from a shop's site should be replaced: ask them, use an official barcode source (GS1 / the maker), or build it from users' own scans (the app already learns barcodes on first scan). |
| **Scalemates** | Nothing. The app only opens a Scalemates search **in your browser** | `ModelPanel.jsx` (`scalematesSearch`) | OK: their robots.txt forbids crawling and the app never fetches them. | **OK** as a plain link. Never add fetching. |
| **Bandai** (bandai-hobby.net) | Nothing: the site is a JavaScript app fed by a private API | – | Not used. | Don't use the private API. Ask Bandai if official data is ever needed. |
| **Colour charts** (e.g. github `sergiogordeev-commits/tamiya-paints`) | Nothing: no licence, so deliberately not used | – | Not used. | Only with a licence or permission. |

**Also check:**
- **User-Agent strings** (`tamiya.HEADERS`, `catalog_import.HEADERS`) say "personal hobby inventory"
  and point at this GitHub repo. A public app must identify itself honestly as what it then is.
- **Request volume.** Per-user lookups multiplied by many users is a different thing for these
  sites. Any shared app should use a single shared cache, rate limits, and the permissions above.
- **Box and product photos users upload themselves** (Milliput, Microscale, build log photos) are
  theirs, but a public app needs terms saying users may only upload photos they have the right to
  use, and a way to take things down.

## 2. Things already in the public GitHub repo

The repo (https://github.com/XDCause/ShelfofShame) is **already public**, so these are already out:

| What | Where | Status |
|---|---|---|
| **Test fixtures copied from other sites**, trimmed to the parts the parser reads (1-7 KB each; long descriptions removed) | `api/tests/fixtures/` (tamiya_*, hasegawa_jt86, hlj_*) | **Check.** Small and mostly facts, kept only so the tests can check the parsers against real pages. For a commercial project, replace them with hand-written fake pages that have the same structure. |
| **Personal details**: Windows user name and folder paths, the spreadsheet's location, the PC's Wi-Fi address (10.0.0.33) and Tailscale addresses (private 100.x addresses, not reachable from the internet) | `README.md`, `CLAUDE.md` | **Change** before promoting the repo: replace with placeholders. CLAUDE.md is a working notebook with the user's own kits, spend and shop; consider making it private or removing it. |
| **No LICENSE file** | repo root | **Change** if others should use the code. Without a licence it's "all rights reserved" by default. Pick one (e.g. MIT), mindful of section 4. |
| Secrets and data | `.env`, `backups/`, `*.dump` | **OK.** Git-ignored; never committed. |

## 3. Built for one person

Fine on a home network with one user; not fine for a hosted app.

| Shortcut | Where | Why it must change |
|---|---|---|
| **No login, no accounts** | whole app | Anyone who can reach port 8080 can view and change everything. A public app needs accounts, and every table needs an owner. |
| **No HTTPS** | `docker-compose.yml`, nginx | Plain HTTP is fine on your own Wi-Fi or Tailscale, not on the internet (and phone camera access needs HTTPS for a live viewfinder anyway). |
| **Backups can be downloaded without a login** | `GET /api/backups/{name}` (`settings.py`) | Hands over the **whole database**. Must be locked to the owner, or removed from a shared app. |
| **CSV export** writes user text as-is | `spending.py` exports | Fine for your own files. With other people's data, guard against "CSV injection": a cell starting with `=`, `+`, `-` or `@` can run as a formula in Excel. |
| **Uploads stored in the database** (product photos, build log photos) | `images.py`, `product_info`, `model_log` | Size/type checks exist (5 MB, images only), but a shared app needs per-user storage quotas, virus/abuse scanning and probably object storage instead of database rows. |
| **Settings are global**: default shop Hobbyrama, prices $3.95 / $10.95 | `db/init/15_settings.sql` | They're the owner's own. Per-user settings, with neutral or empty defaults. |
| **Australia-specific defaults**: time zone Australia/Brisbane, AUD currency, en-AU dates | `db/Dockerfile`, `web/src/api.js` (`money`, `shortDate`) | Make them per-user settings. |
| **Brands list kept deliberately small** (Tamiya, Milliput, Microscale, Other + ones added as used) | `db/init/02_seed.sql` | The owner's choice. A public app would need a proper shared brand list. |
| **One running timer for the whole app** | `build.py` (`GET /api/timer`) | Per user. |
| **No rate limiting** on the API | `api/app/` | Lookups trigger requests to other sites (section 1), so they must be limited per user. |

## 4. Names, brands and design

| What | Status |
|---|---|
| **Third-party trademarks in the app**: Tamiya, Hasegawa, Bandai, Gundam, Gunpla, Warhammer, Citadel, Games Workshop, HobbyLink Japan, Scalemates, Mr. Hobby | **OK** for naming products you own. Commercially: no logos, no wording that implies endorsement, and a "not affiliated with..." line. Games Workshop in particular has strict IP guidelines; read them before shipping anything Warhammer-branded. Gundam is owned by Sotsu/Sunrise (Bandai Namco). |
| **App name "Off the Clock"** (and the module name "Shelf of Shame") | **Check** that no one else uses them as trademarks for similar products, in the countries you'd sell in. "Off the Clock" is a common phrase, so it's likely used by other apps and businesses. |
| **Apple-style design** (Human Interface Guidelines look) | **OK.** It uses the device's own system font (no Apple font files) and our own icons in `web/src/components/icons.jsx`, drawn "in the spirit of" SF Symbols, not copied. Don't add Apple's SF Symbols or SF Pro font files, or Apple's logos or product images. |

## 5. Open-source libraries

All allow commercial use. When you **distribute** the app (not just run it yourself), include
their licence notices:

| Library | Licence | Note |
|---|---|---|
| React, React DOM, React Router | MIT | |
| BlockNote (`@blocknote/core`, `/react`, `/mantine`), the journal editor | MPL-2.0 | File-level copyleft: changes to BlockNote's own files must be shared; using it is fine. Its "XL" add-ons (PDF / Word export, AI) are GPL or commercial - not used. |
| Mantine (BlockNote's menus) | MIT | |
| @zxing/library (barcode reading) | Apache-2.0 | Distribute its licence and any NOTICE file. |
| FastAPI, uvicorn, httpx, Beautiful Soup | MIT / BSD | |
| psycopg 3 | LGPL-3.0 | Fine to use as a library unmodified. If you change psycopg itself and distribute it, those changes must be shared. |
| PostgreSQL, nginx | PostgreSQL licence / BSD-2-Clause | |
| pytest, Playwright (tests only) | MIT / Apache-2.0 | Not shipped with the app. |

## Short version

Before anyone but the owner uses this:
1. **Data sources:** get permission from Tamiya, Hasegawa, HLJ and rchobbyland, or switch to facts plus links and drop the copied photos and hot-linked thumbnails.
2. **Repo:** scrub personal details from README.md and CLAUDE.md, and add a LICENSE.
3. **Security:** add accounts, HTTPS, an owner per row, rate limits, and lock down backups.
4. **Settings:** make shop, prices, currency and time zone per user.
5. **Branding:** add a not-affiliated line and check the app name.

## Already done for safety (review, 2026-10-14)

Safety headers (`web/security-headers.inc`: nosniff, no framing, referrer policy, a content security
policy), web-only links, photo type and size checks on uploads and scraped photos, CSV formula
protection, and dependency audits (`pip-audit`, `npm audit`) were clean at the time. Still needed
before anyone else uses it: **login and HTTPS** (see above) - the headers don't replace those.
