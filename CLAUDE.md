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
- Build and test in dev: `.\dev.ps1` (rebuild), `run_tests.ps1` and `run_e2e.ps1` **in the dev folder**
  (they act on hobby-dev-* containers). `.\dev.ps1 -Refresh` copies prod's data into dev.
- Commit on dev. **Promote only when the user is happy**: `.\promote.ps1` in the prod folder
  (tests dev, backs up prod, `git merge --ff-only dev`, migrate.ps1, rebuild). `-Push` pushes both branches.
- **Schema changes:** a new numbered idempotent db\init file. `migrate.ps1` applies pending files and
  records them in `schema_migrations` (17_schema_migrations.sql). No more hand-piping into psql.
- Plan: docs/ROADMAP.md (core + modules: Home, Journal, Calendar; Board games and Volleyball first).

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

## Stages
1. **PostgreSQL in Docker + schema** - DONE (2026-10-11)
2. **Import the spreadsheet** - DONE (2026-10-11): 22 supplies, total value $142.90
3. **Web app + API** - DONE (2026-10-11). User chose: build API and web together; front end in
   **React (Vite)**. Layout was redesigned in the app refresh (3f) - see there for the current UI.
3b. **Wishlist page** - BUILT (2026-10-11), API smoke-tested; awaiting user's first look.
   - Phone-first cards with product photos; tap a card to tick it off in the shop; filters
     All / To find / Ticked; "You own N" warning; bottom bar "Add N ticked to inventory".
   - Moving to inventory: new supply (qty_wanted, reorder 0, Sealed, today, location Other,
     est_price as unit_price, shop name) or, if brand+code already owned, qty is added instead.
   - Tamiya lookup by item number scrapes tamiya.com (user says Tamiya allows it; no robots.txt
     exists) - one page + one photo per lookup, cached in `product_info`, never re-fetched
     unless `?refresh=true`. Other brands: manual entry, no photo yet.
3c. **Photos in Inventory** - DONE for Tamiya (2026-10-11): thumbnail column, larger photo +
   Tamiya description in the row details, photo + "Get/Refresh photo from tamiya.com" in the
   edit form, and a "Get N Tamiya photos" button (sequential, 1 s pause) when any are missing.
   Backfilled all 20 Tamiya supplies; every code matched the right product.
   **Other brands are ad hoc (user's choice):** "Upload photo" (PhotoUpload component) in the
   supply edit form and the wishlist edit form; on phones it offers the camera. Browser shrinks
   to <=1000 px JPEG on a white background before upload. API: `PUT /api/product-photo?brand_id=&product_code=`
   with the raw image as body (JPEG/PNG/WebP/GIF, <=5 MB), `DELETE` same URL removes it.
   Milliput MIL3 and Microscale MI2 photos were supplied by the user and uploaded: 22/22 have photos.
   Photo URLs carry `?v=<photo_updated>` (product_info.fetched_at) for cache-busting, because
   images are served with a 1-day browser cache.
   Noted typo for the user: SUP-0006 "Craft Bind 20g" is Tamiya "Craft Bond" (not changed).
3d. **Barcode scan -> wishlist** - BUILT (2026-10-11), API tested; camera path awaits a real phone test.
   User chose barcode only; **AI label reading is on hold** (options discussed: local Ollama
   vision model, CPU-only on this laptop so ~30-90 s/photo; or cloud AI = first paid 3rd-party
   dependency). Inventory-side scanning is planned next ("roll it out to inventory after").
   - Wishlist: "Scan barcode" (file input, capture=environment; works over plain HTTP, unlike a
     live viewfinder which would need HTTPS), "+ Add by hand", "Type a barcode".
   - Decoding is in the browser (`web/src/barcode.js`): native BarcodeDetector if present, else
     @zxing/library 0.21.3 (lazy-loaded chunk, ~417 KB), tries 3 sizes x 2 rotations.
   - API `GET /api/scan/{barcode}`: checksum-validated (UPC-A -> EAN-13 with leading 0);
     match "known" (product_info.barcode - reliable), "tamiya" (digits 8-12 happened to be a real
     item number - a GUESS, UI says to check), or "unknown" (for 4950344 barcodes brand_id is
     Tamiya and the form shows the item-number Look up box). Scanning stores nothing;
     `PUT /api/product-barcode` stores it when the user saves the scanned item (the user's photo
     is uploaded too if there's no manufacturer photo).
   - Suggestions prefer the user's own details (supplies, then wishlist) over Tamiya's.
   - `db/init/04_barcodes.sql`: product_info.barcode + partial UNIQUE index.
   - **LESSON (user's first real test failed):** Tamiya barcodes do NOT reliably contain the item
     number. 87038 cement = 4950344 87038 7, but Mini paints differ: 81510 X-10 = 4950344069002,
     81701 XF-1 = 4950344069507. Never calculate barcodes; learn them. Calculated ones were
     removed; the live DB holds only these 3 verified barcodes (X-10 read off the bottle by the
     user, XF-1 from two retailer listings, 87038 from a retailer listing).
   - **No automatic barcode -> item source exists** (checked 2026-10-11): tamiya.com pages don't
     list barcodes; the free UPCitemdb API has no Tamiya paints; Mini paint barcodes are NOT
     sequential (XF-1 06950, XF-10 06959, but XF-76 07005, X-22 06938 - release order with gaps).
     Solution: first sighting = type the label's colour code. `tamiya.item_number()` maps
     Acrylic Mini codes X-n -> 815nn, XF-n -> 817nn (exact; X-20A -> 81520), and the lookup warns
     if Tamiya's title doesn't contain that code. Saving remembers the barcode.
   - Possible later (user's choice): read the X/XF code off the same photo with in-browser OCR
     (Tesseract.js, self-hosted ~10 MB language data, not AI) to skip the typing.
   - **Barcode catalogue (user's idea, 2026-10-11):** `db/init/05_barcode_catalog.sql` table
     `barcode_catalog` (barcode PK -> brand_id + product_code, source, source_url) filled by the
     one-off importer `docker exec hobby-inventory-api python -m app.catalog_import [--refresh]`.
     Source: rchobbyland.com.au Acrylic Mini pages (~104, found via their sitemap); spec table
     gives SKU "81776-A00" + "Barcode #". Checked: robots.txt allows product pages, Crawl-delay 1
     (we use 2 s); terms don't mention automated access, prohibit reproducing content - so we
     store only barcode -> item facts. Never runs automatically; no runtime dependency on the shop.
     Scan order: known (product_info) -> catalog -> digit guess -> unknown (type XF-76).
3e. **Hardening + inventory scanning** - DONE (2026-10-11). User said YES to: git, nightly
   backups, survive reboot, inventory scanning, out-of-stock -> wishlist, stock history,
   automated API tests. User said NO to: MCP server (for now), HTTPS, login.
   - **Git:** installed 2026-10-11 (Git for Windows 2.55). Repo pushed to GitHub (see top).
   - **Backups:** `backup.ps1` (pg_dump -Fc inside the container + docker cp, so no BOM; keeps 14;
     `-CopyTo` for an off-PC copy; logs to backups\backup.log). Scheduled task "Shelf of Shame
     backup" daily 2 am, StartWhenAvailable (runs after wake if missed). Restore was tested into
     a throwaway DB and matched the live data. Older backups\*.sql files (Out-File, have a BOM)
     predate this - prefer the .dump files.
   - **Reboot:** sleep on AC set to never (battery unchanged, 30 min). Docker Desktop autostart
     confirmed working by the user. Lid-close may still sleep.
   - **Stock history:** `db/init/06_stock_history.sql` - table stock_movements + trigger on
     supplies (INSERT / UPDATE OF qty_on_hand / DELETE). Reason via
     `set_config('app.stock_reason', ..., true)` (`db.stock_reason()`); unset = 'manual'.
     Reasons: added, edited, used, bought, bought (wishlist), deleted, import, starting stock.
     item_name snapshot; supply_id SET NULL on delete. API: GET /api/supplies/{id}/history,
     GET /api/history. UI: StockHistory in the item panel.
   - **Inventory scanning:** shared `ScanButton` component. Scan results include supply_id.
     Supply barcode shown = product_info.barcode, else the catalogue's. ScanButton uses a div,
     not a <form> (forms can't nest). Current scan behaviour: see 3f.
   - **Out-of-stock -> wishlist:** now POST /api/wishlist/restock (Out + Low, see 3g); button on Inventory
     when anything is Out; skips items already on the wishlist.
   - **Tests:** `run_tests.ps1` rebuilds `hobby_inventory_test` from db/init/*.sql, runs pytest in
     `docker compose run` with ./api mounted (live app untouched), tamiya.fetch faked; conftest
     refuses non-*_test DBs. 48 tests (supplies, history, wishlist, scan/photos, tamiya parsing
     with saved real pages in api/tests/fixtures). **Run it after every API change.** The
     suite found a real bug on its first run: "(IJN)" became "(Ijn)" -> ACRONYMS list in tamiya.py.
3f. **App refresh** - DONE (2026-10-11), at the user's request ("better integrate things, keep
   it simple"):
   - **Two tabs only: Inventory, Wishlist.** The Add & Edit tab and SupplyForm.jsx are gone.
     "Manage lists" (brands/categories/locations) opens from a gear icon in the header.
   - **Inventory list** slimmed to: photo, item (name + brand · code · size on a second line),
     category, finish, stock (-/+), status, value; columns hide as the screen narrows
     (hide-md 900px, hide-sm 700px, hide-xs 480px). Sorting via a "Sort" dropdown (works on
     phones). Suggestion chips: "Add N out-of-stock to wishlist", "Get N Tamiya photos".
   - **Tap a row -> ItemPanel** (side drawer, full screen on phones): big -/+, Condition and
     Location selects and a Reorder-at stepper that save instantly, Last purchased / Last
     bought from / Notes that save on blur ("Saved ✓"), manufacturer description, photo +
     barcode actions, stock history, "Edit details" (name, category, brand, code, type,
     finish, size, price) and Delete.
   - **Adding = AddPanel**, opened by "+ Add" or by scanning something you don't own: scan or
     type a Tamiya code first, check the fields, then "Add to inventory" (opens the new item)
     or "Add to wishlist". Scanning something you own opens its ItemPanel directly.
   - **Removed "Used for"** (supplies.used_for) and the wishlist's "For project"
     (`db/init/07_remove_used_for.sql`; both were empty). Labels: purchase_date = "Last
     purchased", purchased_from = "Last bought from".
   - **+1 (adjust with delta > 0) sets purchase_date to today**; -1 leaves it alone.
3g. **Condition-driven "Low" + quick filters** - DONE (2026-10-11). User picked all recommendations.
   - Why: everything is qty 1 / reorder 0, so quantity never showed Low. **Condition is the
     fuel gauge.** `db/init/08_condition_low.sql` (CREATE OR REPLACE VIEW): Low also when
     qty = 1 and condition is Nearly empty / Empty / Dried out (a spare bottle keeps it OK).
     "Needs attention" = Out or Low. POST /api/wishlist/restock adds all of those.
   - Top of Inventory: the 5 stat boxes are gone. Now a summary line ("22 items · $142.90",
     "showing N" + Clear when filtering) and tappable chips with counts: Needs attention (+ "Add
     to wishlist"), conditions, categories. InventoryView loads ALL supplies once and filters
     client-side (search also matches notes + barcode), so chip counts always describe
     everything. Brand / Location dropdowns only render when 2+ values are in use; chip rows
     only when 2+ values exist.
   - List: Status column replaced by Condition (+ Low/Out badge only when it applies); rows
     needing attention get an amber left edge. New sorts: condition, needs attention first.
   - Item panel: Condition is a 3x2 grid of tap buttons (Nearly empty/Empty/Dried out shown
     amber when selected) with a hint when that makes it Low. "Reorder at" moved out of quick
     settings into Edit details (DETAIL_FIELDS; SupplyFields `reorder` prop).
3h. **Models tab + filtered totals** - DONE (2026-10-11).
   - Inventory summary follows the filters: "9 of 22 items · $35.55" + Clear filters.
   - `db/init/09_models.sql`: `models` (name, brand_id, product_code = kit code e.g. T61108,
     scale, status Not started/In progress/On hold/Finished, notes, updated_at trigger) and
     `model_paints` (model_id CASCADE, brand_id + product_code, paint_name, **purpose** = what
     it's for, have_it = ticked by hand, sort_order). Paints match the inventory by
     brand + code (not a supply id), so a replaced bottle still counts.
     "have" = owned (qty > 0) OR have_it. Model photo = product_info (brand + kit code).
   - API `app/models.py` router: GET/POST /api/models, GET/PATCH/DELETE /api/models/{id},
     POST /api/models/{id}/paints {text, purpose} (one line or a pasted list: paint, then tab /
     " - " / ": ", then purpose; "(still to buy)" notes dropped; XF-n/X-n -> Tamiya T817nn/T815nn,
     a product code you own, or a Tamiya item number, else unlinked), PATCH/DELETE
     /api/model-paints/{id}, POST /api/models/{id}/wishlist (missing linked paints -> wishlist,
     category Paint, notes "For <model>: <purpose>"; unlinked ones reported as skipped).
     /api/lookups includes model_statuses.
   - UI: Models tab (ModelsView cards: photo, status badge, "Paints 7/9" bar) -> ModelPanel
     (status buttons, checklist with auto-ticked locked rows for owned paints + manual ticks,
     inline "what it's for", tags In inventory / Need to buy / On wishlist / Not linked /
     condition badge when Low, paint name opens its ItemPanel, add one paint with an
     inventory datalist or "Paste a list", notes, photo). Adding a model: Tamiya kit number
     lookup fills name/scale/photo (titles look like "1/48 SCALE MITSUBISHI ...").
   - **The user's first model:** "Mitsubishi A6M3 Zero", Tamiya T61108 (1/48 SCALE MITSUBISHI
     A6M3/3A ZERO (ZEKE)), 9 paints from their list, all owned. Their list said X-10 Gun Metal
     was "still to buy", but SUP-0022 (T81510) is X-10 - told the user.
   - tamiya.TIMEOUT raised 15 -> 30 s (a kit page timed out once).
3i. **Hasegawa kit lookup** - DONE (2026-10-11). For models only (not paints).
   - Scalemates was considered (user's idea) and **rejected**: robots.txt disallows
     /search.php and /products/img for general crawlers, they block many bots and have said
     scrapers flood their servers, fetches got 403, data is community-contributed. Offered
     instead: a "Scalemates link" field on models (not built yet - user chose Hasegawa first).
   - Hasegawa: robots.txt only disallows /hsite/wp-admin/; no terms page found. Use **http://**
     (their HTTPS certificate doesn't validate). Kit pages: /product_g/<series lower>/ with
     #a_item_title, .pacimg (box art; srcset >= 600w preferred, else full size), .a_itemdate_r
     ("Scale … 1:48", "Item no … JT86（09086）", "Category …"). Site search returns 500, so
     item numbers are mapped to series codes: 072nn -> PTnn, 090nn/091nn -> JTnn (verified:
     PT29 = 07229 F-2B, JT86 = 09086 P-40E) and the page's own item number MUST match.
     Other numbers -> ask for the series code (e.g. HC71 = 21171).
   - `app/hasegawa.py` (normalise, series_for_item, fetch, parse) + GET /api/lookup/hasegawa/{code}
     in models.py (series code, item number or HSG<item>; adds brand "Hasegawa" on first use;
     product_info row: product_code HSG<item>, series = series code, description "Item no ... ·
     Scale 1/48 · Category"). ModelPanel: Tamiya | Hasegawa switch for kit lookup; photo
     refresh + "View on" link work for both. Tests: test_hasegawa.py + trimmed fixture.
   - User's next kit added as a model: **P-40E Warhawk, Hasegawa HSG09086 (JT86), 1/48**,
     Not started, no paints yet. (The Zero is now In progress.)
3j. **Run-through + bug hunt** - DONE (2026-10-11).
   - New: `run_e2e.ps1` + `e2e/walkthrough.py` - Playwright (mcr.microsoft.com/playwright/python
     :v1.47.0-jammy, pip installs playwright==1.47.0 at run time) on the hobby-inventory_default
     network against http://web; 21 steps desktop + iPhone 13. It CHANGES data, so the runner
     backs up first and always pg_restores that backup afterwards. Screenshots: e2e/out/
     (git-ignored). Assertions are written against the user's real data (22 supplies, Zero, P-40E).
     **Run it after UI changes** (and run_tests.ps1 after API changes).
   - Bugs found + fixed: (1) "Edit details" saved and closed instantly in ItemPanel and
     ModelPanel - React reused the Edit button DOM node as the submit "Save details" button
     mid-click; fixed with distinct `key`s on footer buttons. (2) Manage lists `uses` counted
     only supplies - now also wishlist, models, model_paints (LOOKUP_USERS in main.py).
     (3) iPhone zoomed into inputs (<16px) - inputs 16px under 700px. (4) Scanned barcode was
     silently not remembered when the new item had no brand+code - now reported.
     (5) Phone header: gear wrapped onto its own line; chips stacked 4 rows - now title+gear row,
     full-width tabs, chip rows scroll sideways. (6) Phone panels: big photo pushed controls
     below the fold - now 88px photo beside the name. (7) Model paint "what it's for" was cut to
     one line - auto-growing textarea. (8) Manual paint tick waited for the server - optimistic.
   - Checked: Tamiya kit pages DO list paints ("Tamiya Colors for brush and airbrush painting":
     30 for 61108, codes like 000X1 / 00X10 / 0XF16, plus sprays 86512... and panel line
     accents) - a broad catalogue list (no XF-76), not curated. Offered as an idea.
3k. **Ideas round 1** - DONE (2026-10-12). User picked 6 of 12 proposed ideas:
   - **Names in the user's style**: `tamiya.your_style_name()` - Acrylic Minis become
     "Acrylic XF2 Flat White" (matches their "Acrylic XF1 Flat Black"); used by suggest() and
     model paint default names. Other titles just tidied (_nice_name + ACRONYMS).
   - **Undo after -/+**: App-level toast "Used one / Added one: <name> · Undo" (6 s). Undo =
     POST adjust {delta: -d, undo: true, purchase_date: <before>} -> reason 'undo', puts the
     last-purchased date back (only if purchase_date is sent). ItemPanel reloads via reloadKey.
   - **Floating Scan button** (phones <=700px only): bottom CENTRE (bottom-right covered the
     list's + buttons), hidden while a drawer is open, lifted above the wishlist buy bar.
     Owned -> ItemPanel, else AddPanel; unreadable photo -> AddPanel + toast.
   - **Scalemates link per model**: `db/init/10_model_links.sql` models.scalemates_url
     (validated to scalemates.com); Edit details field; "Scalemates ↗" link, else
     "Search Scalemates ↗" opening their search in the user's browser. App never fetches it.
   - **Wishlist side panel**: WishForm is now a Drawer (scan / Tamiya code first, like
     AddPanel); WishlistView header "Scan barcode" + "+ Add"; summary "N to find · about $X
     (M without a price)".
   - **Duplicate check**: SimilarItems component (ignores filler words, XF-1 == XF1) in AddPanel
     ("Already in your inventory ... Open") and WishForm ("You already own").
   - Not picked (could revisit): install as phone app (PWA), import Tamiya's kit paint list,
     "used on" models in paint panels, "Wanted" kit status, off-PC backup copy, activity feed.
   - Tests: 80 API, 26 browser steps.
3l. **Inventory -> wishlist** - DONE (2026-10-12).
   - **Automatic**: when a change takes an item from OK to Low/Out (condition -> Nearly empty /
     Empty / Dried out on the last one, or -1 to 0), `auto_wishlist()` in main.py adds it to the
     wishlist with notes "Added automatically: running low / out of stock". Only on that
     transition (stock_status before vs after, same transaction), so removing it from the
     wishlist while still low doesn't bring it back. PATCH and adjust replies carry
     `auto_wish_id`; Undo sends `remove_wish_id` to take it back off (if not ticked).
   - **Manual**: POST /api/supplies/{id}/wishlist (409 if already there) = ItemPanel's
     "+ Add to wishlist" (shows "On wishlist ✓" once there). Supplies carry `on_wishlist`
     (wishlist.ON_WISHLIST: brand+code match, or name when no code); list shows an
     "On wishlist" tag. Shared insert: wishlist.wish_from_supplies() (also used by /restock).
   - Tests: 85 API, 27 browser steps.
   - Wishlist cards show the owned item's state (WISH_SELECT: owned_qty, owned_supply_id,
     owned_condition, owned_status; matched like ON_WISHLIST incl. by name when no code):
     red "None left" (qty 0), amber "You own 1 · Nearly empty" (Low), grey "You own 1 · Sealed"
     (OK = don't double-buy; .badge.own).
   - **Open issue told to the user**: Tailscale access blocked - firewall rule "Hobby Inventory
     web (8080)" has RemoteAddress LocalSubnet; the Tailscale interface is 100.76.51.75/32, so
     the phone (100.118.29.60) is outside it. Fix (admin): Set-NetFirewallRule -DisplayName
     "Hobby Inventory web (8080)" -RemoteAddress LocalSubnet,100.64.0.0/10. Check whether done.
3m. **Shop Tamiya** - DONE (2026-10-13). User wanted to search e.g. "Tamiya Panel Line Black" and
   add it to the wishlist without knowing the item number.
   - `db/init/11_catalog.sql`: `catalog_products` (brand_id + product_code PK, item, title, genre,
     thumb_url = Tamiya's CDN, source_url). Filled by the one-off importer
     `docker exec hobby-inventory-api python -m app.tamiya_catalog` (`app/tamiya_catalog.py`):
     tamiya.com/english/products/list.html?genre_item=e_5040|e_5010|e_5020|e_5030 (Paints,
     Finishing Materials, Craft Tools, Airbrush System), 2 s between pages, ~54 pages. First run
     2026-10-13: 1,012 products. Never runs automatically.
   - API `app/catalog.py`: GET /api/catalog/search?q= (every word must match the title, hyphens
     ignored; XF-76 / xf76 -> item 81776; owned first, with owned_* + on_wishlist), GET /info,
     POST /api/catalog/{code}/wishlist (409 if already on the wishlist). **Adds instantly** from
     the catalogue title (suggest(title, genre)), then a BackgroundTask fetches the page + photo
     (tamiya_product) and fills in size/type/finish/category only where empty. Why: tamiya.com
     takes 0.5-5 s per page, sometimes far longer (30 s timeout x page + photo = ~1 min waits).
     If the fetch fails the wish stays, just without a photo (logged). Wishlist rows carry
     `catalog_thumb` (Tamiya CDN thumbnail) shown until the real photo exists.
   - UI: "Shop Tamiya" button on the Wishlist -> ShopPanel drawer (search as you type, suggestion
     chips, thumbnails hot-linked from Tamiya's CDN with no-referrer, OwnedBadge, "+ Wishlist").
     OwnedBadge moved to its own component.
   - Tests: 91 API (test_catalog.py + trimmed fixture tamiya_list_e_5010.html), 28 browser steps
     (catalogue search only; thumbnails are blank in its screenshots). NOTE: the e2e's Tamiya (XF-2) and
     Hasegawa (PT29) lookups DO fetch those sites each run - its data restore removes the cached rows.
3n. **Usual prices, item ranges, removing used-up items** - DONE (2026-10-13).
   - `tamiya.suggest(title, series, description, item)`: Tamiya item-number ranges fill paint type
     and size (ITEM_RANGES: 815/817 Acrylic Mini 10ml, 810/813 Acrylic 23ml, 800/803 Enamel 10ml,
     821 LP Lacquer 10ml, 850/851/865 TS/AS Lacquer 100ml, 860 PS 100ml; "ACRYLIC ... MINI" in
     the title wins - some minis are 813xx). Panel Line Accent = Enamel 40ml (pages have no
     description). Finish fallback: XF- = Flat / Matt, X- = Gloss.
   - **PRICE_GUIDE (user's numbers):** every 10ml Acrylic = $3.95, Panel Line Accent = $10.95.
     Returned as `est_price` by suggest(); used for wishlist est_price (catalogue add, model
     "missing to wishlist" - which now also falls back to catalog_products when the page was
     never fetched) and prefilled in AddPanel / WishForm price fields (applyResult; String()!).
   - `tamiya.tidy()`: NFKC normalises Tamiya's full-width brackets "（DARK BROWN）".
     your_style_name and suggest use it. Fixed live: wishlist T87140 and SUP-0023.
   - **Removing**: DELETE /api/supplies/{id}?also_wishlist=true also deletes the matching
     un-ticked wishlist row (wishlist.ON_WISHLIST_MATCH). ItemPanel: amber "All used up. Not
     replacing it?" box (qty 0, or last one Empty / Dried out) -> "Remove from inventory";
     footer "Delete" renamed "Remove". Toast after using the last one: Undo + "Not replacing?"
     (opens the item). Toast now takes several actions. History reason stays 'deleted'.
   - e2e reads TOTAL / PAINTS from the API instead of hard-coding 22 / 9.
   - Tests: 104 API, 29 browser steps.
3o. **Lifetime spend** - DONE (2026-10-13). User asked for it, "can be hidden".
   - `db/init/12_spend.sql`: stock_movements.unit_price, set by the trigger from the supply's
     price at that moment (OLD.unit_price on delete). Older rows backfilled with the current
     price. The Dark Brown panel line (T87140, SUP-0023) was a TEST, never bought: its 3 history
     rows were deleted on the user's request (2026-10-13).
   - GET /api/spending (main.py PURCHASES/SPEND): purchases = added, bought, bought (wishlist),
     starting stock, import (change > 0) x unit_price, minus 'undo' rows with change < 0.
     used / deleted / edited / manual don't count. Returns all_time, this_year, this_month,
     starting_stock, unpriced, by_year, recent (10, excluding starting stock).
   - UI: `Spending` component = closed <details> at the top of the gear (Manage lists) drawer;
     loads only when opened. Brands / Categories / Storage locations are closed <details> too
     (shared `.fold` style). After removing the test: $146.85 all time ($142.90 starting stock).
   - Inventory summary "$142.90" is CURRENT stock value (qty x price), not spend.
   - Tests: 105 API, 29 browser steps.
3p. **Kit stash, time, build log, colours, settings, Apple-style refresh, clean-up** - DONE
   (2026-10-13). User asked for all of it in one go.
   - **DB** (each applied live after a backup): `13_kit_stash.sql` (statuses Wanted / In stash /
     In progress / On hold / Finished / Gone - 'Not started' became 'In stash'; price_paid,
     purchase_date, purchased_from, started_on, finished_on; `model_sessions` (ended_at NULL =
     running, partial UNIQUE = one running per model); `model_log` (date, text, photo BYTEA);
     product_info.kit_paints JSONB), `14_colours.sql` (colour_groups + members, mixes + mix_parts,
     model_paints.mix_id ON DELETE SET NULL), `15_settings.sql` (settings key/value with
     default_shop = Hobbyrama; price_guide rules seeded with the user's 3.95 / 10.95).
   - **Kit stash**: "shelf of shame" = In stash + In progress + On hold (GET /api/models/summary:
     kits, value of price_paid, unpriced). Status In progress / Finished fills started_on /
     finished_on if empty. Spending also reports kits_spent (non-Wanted price_paid).
   - **Time**: one timer at a time (starting one stops others); starting it moves Wanted /
     In stash / On hold to In progress. Manual time = minutes on a day (12:00 local). Banner at
     the top of the app while a timer runs (GET /api/timer).
   - **Build log**: dated notes + optional photo (browser shrinks to 1600 px), newest first.
   - **Kit paint lists**: tamiya.parse_kit_paints reads div.item_colors_used_ (h3 groups,
     .ttl_ names, "ITEM No.xxxxx"). Each paint gets a `section` number because Tamiya gives the
     LP list and the X/XF list the SAME heading. Generic colour items (000X7, 0XF62 - not all
     digits) map to the Acrylic Mini (T815nn/T817nn) and are pre-ticked; LP / sprays /
     weathering / tools are offered unticked. Cached in product_info.kit_paints; `?refresh=true`
     re-reads once. Picker labels: "Lacquer paints (LP)", "Acrylic paints (X / XF) - as Acrylic
     Minis", "Spray cans".
   - **The user's Sherman** (model 3): Tamiya T32595 1/48 M4A3E8 "Easy Eight", In stash, no
     price yet, 12 X/XF paints from the kit list (owns 2: X-10 Gun Metal, XF-1).
   - **Colours** (colours.py): `tamiya.colour_of(name)` -> (code, colour name) after stripping
     range words; GREY->GRAY; thinners aren't colours. Matches: same code (X-7 Mini = X-7 enamel =
     X-7 jar; generic catalogue pages excluded), same name (LP-28 / TS-5 / XF-62 Olive Drab:
     "likely close"), your colour groups. **No cross-brand chart is built in**: the only open
     dataset found (github sergiogordeev-commits/tamiya-paints) has NO licence, so it can't go in
     this public repo; Tamiya's pages don't state LP<->XF equivalents either. Mixes: recipe text
     "XF-62 + XF-2 (3:1)" / "XF-62 3 + XF-2 1" (paints.parse_mix); a pasted checklist line with
     "+" becomes a mix; have = every part owned; missing parts go to the wishlist.
     Checklist lines you don't have show `alternative` = a supply you own with the same code /
     same name / in your group.
   - **Used on**: supplies carry used_on (models whose checklist has it, directly or in a mix);
     item panel chips open the model; the "used up" box mentions them.
   - **Settings panel** (gear): Spending, Price guide (first matching rule wins; conditions:
     name contains / paint type / size, "10 ml" == "10ml"), Default shop (buy with a blank
     shop = default; new items and kits pre-fill it), Backups (API runs pg_dump 17 - installed
     from apt.postgresql.org in api/Dockerfile - into ./backups mounted at /backups; same file
     names/log/keep-14 as backup.ps1; download link), Export to CSV (UTF-8 BOM for Excel),
     Tamiya catalogue refresh (BackgroundTasks + module-level REFRESH state, polled every 2 s),
     Brands / Categories / Storage locations. Every section is a closed `Fold`.
   - **Apple HIG refresh** (styles.css rewritten): system font, systemBlue tint, grouped
     background, inset grouped lists/panels, filled / tinted (`secondary`) / `plain` /
     `destructive` buttons (old `link` / `danger-link` classes are gone), segmented control,
     capsule chips, translucent nav bar with Scan + Settings; phones (<=700px): bottom tab bar
     (Inventory, Wishlist, Models, Colours), sheets slide up with a grabber, 44px targets; dark
     mode via system colours. The floating Scan button was replaced by Scan in the nav bar; the
     Inventory toolbar's own scan was removed (typing a barcode is in the Add panel, which now
     opens an item you already own). Drawer keeps a stack: Esc closes only the top panel.
   - **Clean-up**: API split into modules - supplies, wishlist, products (lookups, scan,
     barcodes, photos), catalog, models, build, colours, paints (typed paint -> product, shared),
     spending (+ CSV), settings, lookups, images (upload rules); main.py only wires them.
     db.py has insert_row / update_row / found / brand_id helpers (replacing 4 copies of the
     SQL-building code). tamiya._nice_name -> nice_name (public), Roman numerals stay capitals.
     Front end: api.js grouped by area; ModelPanel split into ModelForm, PaintChecklist,
     KitPaintsPicker, TimeTracker, BuildLog; new Fold, Elapsed, icons, SettingsPanel,
     PriceGuide, ColoursView, ColourMatches. pyflakes clean; no unused imports or CSS.
   - **Tests**: 159 API (new test_settings, test_build, test_colours; fixture
     tamiya_kit_32595.html is a trimmed copy - title + paint list only), 37 browser steps
     (counts of supplies / models are read from the API at the start).
   - **Lesson**: `docker compose up -d api` does NOT rebuild - code changes need
     `docker compose up -d --build api` (the Sherman's paint list was first read by a stale
     image and had to be refreshed).
3q. **Full-width nav bar + grouped inventory** - DONE (2026-10-13).
   - User saw "big black bars" down the sides on their desktop (dark mode): the nav bar stopped
     at the 1200px column. Now `.navbar` spans the window and `.navbar-row` / `.content` share
     the centred column (`--column`, `--gutter` on `.app`).
   - Inventory is grouped into drop-down cards (same `.fold` look as Settings): Group by
     category (default) / condition / needs attention / brand / location / no groups. Header shows
     count, value and "N need attention". Choice + CLOSED groups remembered in localStorage
     `hobby-inventory.inventoryGroups` (closed stored, so new groups appear open). Searching or
     filtering opens every group with a match; closing while filtering is temporary. "Close all /
     Open all". Each group is its own table with fixed column widths (quiet zero-height thead)
     so columns line up; Category column dropped when grouped by category.
   - Tests: 38 browser steps (new "Groups" step).
3r. **Hobbies: Warhammer and Gundam** - DONE (2026-10-13). User chose both together, but NO
   Citadel paints / paint "range" yet ("wouldn't bother at this stage"); they mainly use Tamiya
   Panel Line colours.
   - `db/init/16_hobbies.sql`: models.hobby (Scale model / Warhammer / Gundam, default Scale model),
     stage (last build step done; CHECK per hobby), grade (Gundam), faction (Warhammer army),
     figures / figures_done (minis in a box). db.py STAGES / HOBBIES / HOBBY_BRANDS / GUNDAM_GRADES
     (grade -> usual scale) must match; /api/lookups returns them.
   - models.tidy_model(): brand_name adds a brand on first use (db.ensure_brand, also used by the
     Hasegawa lookup); a stage must be the hobby's; changing hobby drops a stage it lacks; ticking
     a step on Wanted / In stash / On hold -> In progress; fewer minis than done -> done lowered.
   - UI: hobby segmented picker in ModelForm (new Warhammer/Gundam kit pre-selects Games Workshop /
     Bandai, shown as "(new)" until saved), Grade with datalist (fills scale), Army, Minis in the
     box; Tamiya/Hasegawa lookup only for Scale model; no Scalemates for Warhammer. BuildSteps
     component (numbered dots, tap last ticked to untick, minis stepper). ModelsView: hobby filter
     (only when 2+ hobbies), cards show "Panel lined, step 2 of 4" / "3 of 10 minis painted".
     Models CSV has Hobby / Grade / Army / Build step / Minis columns.
   - **Bandai's own site isn't usable**: bandai-hobby.net is a JavaScript app (every URL returns the
     same shell; data comes from a private API). Superseded by the HLJ lookup (3s).
   - **The user's Gundam**: model 5 "RX-78-2 Gundam (Revive)", Bandai (brand added) G5057403 (user's
     code), HG 1/144, In stash, notes "HGUC 191", no photo/price; checklist Panel Line Gray (owned,
     white parts) + Panel Line Black T87131 (not owned, blue/red/yellow parts).
   - Live data seen 2026-10-13 (user's own edits): Sherman and P-40E now Wanted, new model 4
     Triceratops Eurycephalus (Tamiya T60201, 1/35, On hold).
   - Also fixed: model cards without a photo collapsed (.model-photo width 100%); status badges wrapped.
   - Tests: 167 API, 40 browser steps (gundam, warhammer).
3s. **Bandai lookup via HobbyLink Japan + BEFORE_GOING_PUBLIC.md** - DONE (2026-10-13).
   - User: "Photos are key. Its an internal tool just for me so it should be fine. Good to note if
     this was to be made commercial" -> photos ARE cached; every such caveat goes in
     **BEFORE_GOING_PUBLIC.md** (repo root). **Rule: whenever a new data source, scraper, copied
     content or single-user shortcut is added, add a row there.**
   - Sources checked 2026-10-13: hlj.com robots.txt allows product + search pages (only /account/,
     /relatedproducts/, /recommendproducts/ blocked); their Copyright page reserves text/images;
     Terms page is behind Cloudflare (not bypassed). Rejected: gundam.fandom.com (Cloudflare bot
     challenge), dalong.net (reviews, not a catalogue), Hobbyrama (robots allows product pages,
     Crawl-delay 10 for bots, /search.php disallowed; not checked further - maybe later for AUD prices).
   - `api/app/hlj.py`: kit pages have schema.org Product JSON-LD (name, sku = HLJ code, gtin13 =
     barcode, image) + `.product-details li` (Series, Item Type, Release Date, Manufacturer).
     Search `/search/?q=` works in plain HTML (`.search-widget-block`, code from `[id$=_stock]`);
     only BAN* results kept. Bandai Spirits barcodes = 4573102 + last 5 digits of the item number
     + check digit (G5057403 -> 4573102574039): used only as a SEARCH key, and the page's gtin13
     must match (the Tamiya "never calculate barcodes" lesson still holds for storing).
     product_code_for(): G50xxxxx for 4573102 barcodes, else the HLJ code. Grade from the title
     (HGUC/HGCE -> HG, Entry Grade -> EG, RE/100, Full Mechanics -> FM...).
   - `GET /api/lookup/bandai/{code:path}`: code / barcode / HLJ code / name. A name with several
     results returns {"choices": [...]} (no page fetched); picking one looks it up by hlj_code.
     One lookup = search + page + photo with 1 s pauses; cached in product_info (description
     "High Grade Kits · Gundam 0079 · Released 2025/04/30 · HLJ BANH574039-UP"; barcode stored
     if no other product has it). Cache matches product_code, barcode or source_url ending in the
     HLJ code.
   - UI: Gundam in ModelForm gets the lookup (Bandai, "Scan the box" via ScanButton, pick list
     with HLJ thumbnails hot-linked no-referrer); ModelPanel "Get/Refresh photo from hlj.com" and
     "hlj.com ↗" link (SOURCES map).
   - The RX-78-2 (model 5) was looked up live once: photo, barcode 4573102574039, HLJ page.
   - Tests: 196 API (test_hlj.py + trimmed fixtures hlj_banh574039.html, hlj_search_rx78.html),
     41 browser steps (bandai_lookup uses the cached kit - no hlj.com fetch).
3t. **Dev and prod** - DONE (2026-10-13). User asked for prod and dev environments "so this can
   be better tested before pushing such big changes", as phase 0 of a big plan (Notion-like
   journal, calendar, UI rewrite, a module per hobby; docs/ROADMAP.md). User's choices: Notion-style
   block editor (BlockNote), **a new umbrella app name (not chosen yet - ask at phase 1)**, Board
   games + Volleyball as the first new modules, dev and prod both on this PC.
   - docker-compose.yml: `name:`, container/image names `${APP_PREFIX:-hobby-inventory}-*`, volume
     `${DB_VOLUME:-hobby_pgdata}`, api env `APP_ENV`. Prod's resolved config is unchanged (checked).
   - Dev .env (written by dev.ps1 -Setup): APP_PREFIX=hobby-dev, APP_ENV=dev, ports 5434/8001/8081,
     DB_VOLUME=hobby_dev_pgdata; same DB name/user/password.
   - scripts\common.ps1 (dot-sourced): reads .env -> $Prefix, $DbContainer, $Network, ports,
     Wait-Healthy. start/backup/run_tests/run_e2e use it.
   - GET /api/about -> {"env"}; the web app shows an orange DEV badge and "[DEV]" in the tab title.
   - The Windows firewall rule only opens 8080, so phones can't reach dev on 8081 unless another
     rule is added (not done).
   - Tests: 197 API, 41 browser steps, run in both copies.
3u. **Phase 1: new UI shell, "Off the Clock"** - DONE in dev (2026-10-13). User picked the name.
   - React Router 7.6.2 (`react-router`, BrowserRouter in main.jsx; nginx already falls back to
     index.html). Addresses: `/` Home, `/models/inventory|wishlist|kits|colours`, `/models` ->
     inventory, anything else = "There's no page here" + Go home.
   - `web/src/modules/index.js` = MODULES registry; `modules/models/manifest.jsx` (id, name "Shelf
     of Shame", what, Icon, HomeCard, pages [{path, label, Icon, render(app)}]). The view
     components stay in web/src/components for now (not moved).
   - `core/app-context.js` (AppContext: lookups, settings, refreshKey, changed, openItem,
     openModel, openAdd, adjusted, showToast), `core/Home.jsx` (date, greeting, each module's
     HomeCard), `core/Navigation.jsx` (Sidebar: brand, Home, "Hobbies", module + its pages;
     TabBar on phones: Home + the current module's pages).
   - `modules/models/ModelsHome.jsx`: 4 stat tiles (links: Needs attention, To buy, Shelf of shame,
     Time building), "Building now" (In progress kits, opens the panel), latest 5 stock changes
     (GET /api/history?limit=5).
   - Layout CSS: `.app` grid (sidebar 236px | main-col); 701-1000px icons-only sidebar (64px);
     <=700px no sidebar, `.tabbar a` (NavLink aria-current). The nav bar title = page label with
     the module name above it (`.nav-context`); document.title "Inventory · Shelf of Shame",
     "[DEV] ..." in dev. Panels, toast, timer banner, Scan + Settings unchanged.
   - e2e: `go(page, name)` clicks the nav link (sidebar or tab bar); new Home step; phone step uses
     `.tabbar a`. 197 API tests, 42 browser steps (dev).
3v. **Phase 2: Journal** - DONE in dev (2026-10-13). The user wasn't sure about the phase 1 look
   ("I'm not sure i love it") and said to keep prod as it is, keep developing in dev and review later.
   **Don't promote until the user has reviewed dev.**
   - `db/init/18_journal.sql`: journal_pages (title, icon, entry_date, content JSONB = BlockNote
     blocks, text = plain text for search, pinned, updated_at trigger), tags + page_tags (unused
     tags deleted), journal_links (page -> model / supply / page, from @mentions, rebuilt on each
     save), journal_images (BYTEA). Applied to dev with migrate.ps1.
   - `api/app/journal.py`: plain_text() / mentions() walk the blocks (mention = inline
     {type: "mention", props: {kind, ref, label}}); GET /journal (q = every word in title or text,
     tag, mention=kind:id; pinned first, then date), POST, GET/PATCH/DELETE /journal/{id} (links,
     mentioned_in), /journal/tags, /journal/mentionable?q= (8 each of models / supplies / pages),
     POST /journal/images (read_photo rules) + GET. Tests: test_journal.py (12).
   - Front end: BlockNote 0.54.2 + @mantine/core 8.3.18 (`web/src/core/journal/`): Editor.jsx
     (lazy-loaded chunk ~0.9 MB, 335 KB gzipped; custom `mention` inline spec, `@`
     SuggestionMenuController -> /mentionable, uploadFile shrinks to 1600 px, theme follows
     prefers-color-scheme; clicking a pill opens the model / supply panel or the page),
     JournalPage.jsx (autosave 700 ms after typing, flush on leave; reply only refreshes links so
     typing isn't overwritten), JournalList.jsx (search, tag chips, Pinned + month groups;
     useNewPage, PageRow), JournalHome.jsx (Home card: "Write today's entry" = page titled with
     today's date, latest 3), JournalMentions.jsx ("In the journal" + "+ Write about it" in
     ModelPanel and ItemPanel), TagsInput.jsx.
   - Navigation: CORE_PAGES (Home, Journal) in core/Navigation.jsx. Phones: tab bar = Home, Journal,
     one tab per hobby (manifest `short`: "Shelf"); a hobby's pages = `.module-tabs` segmented
     control under the nav bar (ModuleTabs).
   - nginx: gzip on for css / js / json / svg.
   - e2e: journal_write / journal_links / journal_from_model (MARK = unique word per run, so pages
     already in the data don't matter); phone step uses the Shelf tab + .module-tabs.
     209 API tests, 45 browser steps (dev).
3w. **Journal actions, to-dos, margins** - DONE in dev (2026-10-13). User: "I like the journal";
   margins were off; wants "I just bought @model and started it right away" to move it to In
   progress, and to check things off (calendar / to-do list later). Still NOT promoted.
   - Margins: `.journal-page` has a left gutter (`--gutter-left` 60px, 16px on phones); the editor
     gets `margin-left: -gutter` and `.bn-editor` `padding-inline: gutter 0`, so title, date/tags
     and body text share one left edge and the drag handle sits in the gutter. Emoji box 1.3em,
     left-aligned. Our global `input` styles were hitting BlockNote's checkboxes: reset in
     `.journal-editor input[type=checkbox]`.
   - `db/init/19_journal_actions.sql`: journal_pages.dismissed TEXT[].
   - `api/app/journal_text.py` (inline_text / plain_text / mentions, moved out of journal.py) and
     `api/app/journal_actions.py`: suggestions(conn, page) per block that mentions a model:
     STATUS_WORDS (bought -> In stash only from Wanted, started -> In progress from Wanted / In
     stash / On hold, on hold, finished, sold -> Gone) and STEP_WORDS (built, primed, painted,
     panel lined, decals, weathered, top coat, based; only the hobby's steps, only forward). The
     word written LAST in the block wins. In stash adds purchase_date, In progress started_on = the
     page's date (if empty). Key "model:<id>:<field>:<value>"; dismissed keys skipped.
     todos_in(page) / set_checked(content, block_id) for checkListItem blocks (need BlockNote ids).
   - journal.py: fetch_page adds `suggestions`; POST /journal/{id}/suggestions/apply (re-checks
     the offer, then models.update_model with the changes; 409 if no longer offered) and /dismiss;
     GET /journal/todos?done=; PATCH /journal/{id}/todos/{block_id} {checked}.
   - UI: JournalPage shows suggestions under the text ("@Name Mark as ...?" Yes / Not now; Yes
     flushes pending edits first, toasts "Name: now In progress"); TodoList.jsx (Journal page card
     + Home first 5; a ticked item stays struck through until reload so it can be unticked).
     JournalHome: "Latest pages" heading. Phones: toolbar search flex-basis 140px so "+ New page"
     fits beside it.
   - e2e: journal_suggestion (makes a Wanted "Kit-<MARK>" via the API), journal_todo (/check in the
     editor; focus + Control+End, since clicking mid-line can hit a mention pill).
     215 API tests, 47 browser steps (dev).
3x. **Creative refresh + journal -> wishlist** - DONE in dev (2026-10-13). User sent two reference
   designs (one "Shelf of Shame" dark navy dashboard, one "Off the Clock" journal/inventory) and
   asked to "up the creativity", pulling the best of each. Still NOT promoted.
   - Journal: supply mentions + BUY_WORDS ("want to buy", "need more", "order", "running low on",
     "ran out of"...; NOT "bought") -> "Add to wishlist" (key supply:<id>:wishlist:yes; applied with
     wishlist.wish_from_supplies, notes "From the journal: <title>"); skipped if already on it.
   - `api/app/activity.py`: GET /api/activity?limit&since - UNION of stock_movements (added /
     bought / used / deleted), models' purchase_date / started_on / finished_on (at noon; Wanted kits'
     purchase dates skipped), model_log, stopped model_sessions, journal_pages; product photo
     joined. Journal list rows: cover_url (first image block) else product_info of the first
     mentioned kit / supply (LATERAL).
   - Theme: `core/theme.js` sets <html data-theme> (localStorage `offtheclock.theme`: system /
     light / dark; Settings > Appearance). CSS tokens: light + `:root[data-theme='dark']` navy
     (#0a0f1c bg, #111a2c surface); new tokens --border, --sidebar, --tint-2, --teal, --hero-shade.
     No more prefers-color-scheme in CSS; the editor uses useTheme(). Cards / panels / folds get a
     1px --border.
   - Tone classes `.tint .ok .low .out .purple .teal` set --tone / --tone-bg for `.pill`,
     `.stat-icon`, `.thumb-icon`, `.fill-bar`.
   - Home (core/Home.jsx): hero (photo of the latest kit in the activity feed, gradient shade,
     daily TAGLINES, "Write today's entry"), each module's `home.Stats`, grid [Recent activity |
     Quick actions + JournalHome], each module's `home.Cards`. Manifest `home: {Stats, Cards}`
     replaced HomeCard; models: ModelsStats / ModelsCards (Building now with step bars, Running low
     with fill bars) sharing one fetch via core/useShared.js.
   - modules/models/fill.jsx: FILL by condition (Sealed 100, Opened 85, Half used 50, Nearly empty
     15, Empty / Dried out 0), FillBar; used in Home, the inventory Condition column, ItemPanel.
     Inventory Category column = CategoryPill (colour from a hash of the name).
   - core/GlobalSearch.jsx in the nav bar (uses /journal/mentionable; Ctrl/Cmd+K; arrows + Enter;
     phones: a search button that opens the box over the title). Sidebar: brand mark + daily
     "nudge" card. Journal list = PageCard (date block, picture, first tag pill, two-line snippet,
     tags, Pinned) + Newest / Oldest sort. Home's Shop Tamiya -> /models/wishlist?shop=1 opens it.
   - Gotcha: on phones a single grid column must be `minmax(0, 1fr)`, not `1fr` (which won't
     shrink below a long one-line title and widened the page).
   - e2e: inventory search is `get_by_label("Search", exact=True)` (the top bar has "Search
     everything"); new steps global_search, journal_wishlist, appearance. 221 API tests, 50 steps.
3y. **Change log round + structure + Calendar, Board games, Volleyball** - DONE in dev (2026-10-13).
   Still NOT promoted (user reviews dev first).
   - Item panel: "On wishlist ✓ ✕" takes it off (DELETE /api/supplies/{id}/wishlist, 409 if not on it
     or ticked); photo buttons behind a "Photo options" drop-down, barcode stays visible.
   - ScanButton is now one "Use barcode" button offering "Scan with camera" / "Type the number".
   - Wishlist: per-card "Bought" removed - tick, then the bar's "Add N to inventory" (no confirm).
     Header is just "+ Add"; the add panel (WishForm) starts with CatalogSearch (was ShopPanel)
     + Use barcode + the form. /wishlist?add=1 opens it (Home's Wishlist action). Page messages
     use components/Notice.jsx (✕ to close; ok ones fade after 8 s).
   - Build steps: modules/models/steps.jsx buildProgress(): an In progress kit's next step is
     "underway" (half-filled dot, striped segment, "Now: Priming"; text "Priming · step 2 of 5").
   - Structure: core pages Home, Journal, Calendar, Supplies (/supplies, title "Hobby supplies"),
     Wishlist (/wishlist); /models/inventory and /models/wishlist redirect. Modules: models (Kits,
     Colours), boardgames (Games, Plays), volleyball (Games, Gear, Videos). Sidebar = core + one
     link per hobby; a hobby's pages are SectionTabs on every width. Phone tabs: Home, Journal,
     Calendar, Supplies (Supplies | Wishlist tabs), Hobbies (/hobbies page with each hobby's tiles).
     Manifest: home {Tiles, Cards}, actions (Home quick actions), panels {type: Component};
     App opens them with openPanel(type, props); openThing(kind, id) opens any activity / search /
     mention target. core/Stat.jsx, core/SuppliesHome.jsx (supplies tiles + Running low),
     core/activityKinds.js, components/RecordFields.jsx (field specs -> form + payload; RowPhoto).
   - DB: 20_calendar.sql (calendar_events: repeats never/weekly/fortnightly, repeat_until,
     skipped DATE[]), 21_board_games.sql (board_games with photo columns, board_game_plays),
     22_volleyball.sql (gear with hobby column for later modules, volleyball_games with event_id,
     volleyball_videos = links only). journal_links kinds + 'game', 'gear'.
   - API: calendar.py (days_of expands repeats; /calendar returns events + activity.rows for the
     range; logged_id per volleyball occurrence), boardgames.py, volleyball.py,
     images.add_photo_routes (photo on the row), db.tidy_text. activity.py now returns `day` and
     `photo_url` (not product_info_id) and has `until`; journal pages sit on their entry_date.
     Journal: "played @Catan" -> "Log a play" (PLAY_WORDS, key game:<id>:play:<date>).
   - Gotcha: the Bash tool chokes on some heredocs with quotes/backslashes - write a .py file with
     the Write tool in the scratchpad and run it instead. NavLink sets its own aria-current (the
     phone tab bar uses Link to mark Supplies active on /wishlist).
   - Tests: 239 API, 54 browser steps.
3z. **Review: security, speed, tests** - DONE in dev (2026-10-14), user asked for "a big check over
   everything". pyflakes clean; ESLint (react + hooks, throwaway config, not in the repo) leaves 3
   deliberate exhaustive-deps warnings (ModelPanel, SettingsPanel, useShared: run once per id / key).
   - Security: nginx `web/security-headers.inc` (nosniff, X-Frame-Options, Referrer-Policy, CSP:
     scripts/connect only 'self', images also https:/data:/blob:, inline styles allowed) included in
     the server AND each location that sets its own headers (nginx add_header inheritance);
     client_max_body_size 6m (default 1 MB < the API's 5 MB). bgg_url must be http(s) (React 19
     already blocks javascript: hrefs; now the API refuses them too). images.fetched_photo(): photos
     scraped from Tamiya / Hasegawa / HLJ only if JPEG/PNG/WebP/GIF <= 5 MB (was any image/*, incl.
     SVG which can carry script; one helper instead of three copies). CSV cells starting with = + - @
     tab CR get a leading ' (spending.cell). Backups download already only serves the name pattern.
   - Dependencies: pip-audit + npm audit now clean. fastapi 0.115.12 -> 0.143.0 (Starlette 0.46 ->
     1.8, several advisories), uvicorn 0.54.0, pytest 9.0.3, react-router 7.6.2 -> 7.18.4 (XSS
     advisories). Starlette now warns that TestClient wants `httpx2` - harmless, left for now.
   - Speed: psycopg_pool ConnectionPool in db.py (new connection ~6 ms vs ~0.1 ms query; most
     requests ~2x faster), check_connection on checkout (survives DB restarts), opened lazily under
     a lock, closed atexit (otherwise uvicorn / pytest waited 5 s per pool thread on exit). Photos
     served with Cache-Control 1 year immutable + nosniff - so EVERY photo URL must change with the
     photo: versions are now milliseconds (were whole seconds: a photo replaced twice in a second
     kept its URL - the new test caught it), and model_log got photo_updated (23_review.sql; its URL
     used created_at, which doesn't change when the photo is replaced). /assets/ cached 1 year
     (hashed names), index.html no-cache. 23_review.sql also indexes 10 foreign keys. Home's
     board-games tiles fetch only the summary.
   - Removed: unused api.js wrappers (recentHistory, updatePlay, updateLogEntry), CloseIcon,
     PlusIcon, ItemPanel longDate, InventoryView lookups prop. Kept /api/supplies/low-stock (for the
     stage-6 assistant). CSV exports added: board-games, plays, volleyball, gear; file names
     off-the-clock-*.
   - Tests: 249 API (new test_safety.py: links, uploads, served-photo headers, scraped-photo checks,
     CSV formulas, 20 concurrent requests on the pool, rollback, calendar repeat edges; log photo
     re-versioning in test_build.py), 54 browser steps (CSP violations would show as browser errors).
3za. **Drawing in the journal (pen / whiteboard)** - DONE in dev (2026-10-14). User: journal "more like
   reMarkable crossed with whiteboard crossed with notion", drawing with a Samsung Tab S7 + S Pen,
   "draw images not just text". Still NOT promoted.
   - Library: **Excalidraw 0.18.1** (MIT; tldraw was the alternative but needs a licence key in
     production). Pressure from pointer events; pen mode turns on by itself when a pen is used
     (pen draws, fingers pan/zoom = palm rejection). Canvas always opens with the pen tool.
   - DB 24_drawings.sql: journal_pages.kind notes|whiteboard; journal_drawings (page_id CASCADE,
     board bool - one per whiteboard page, partial unique; scene JSONB {elements, appState: bg +
     grid only}; files JSONB {fileId: {mimeType, dataURL}} merged with `||`; text from text
     elements (page search includes it via page_text); preview PNG BYTEA).
   - API journal_drawings.py (router included before journal): POST /journal/{page_id}/drawings,
     GET/PUT/DELETE /journal/drawings/{id} (can't delete a board: 409), PUT .../files, GET/PUT
     .../preview (?v= ms of updated_at). Page save: drop_unused() deletes sketches no "drawing"
     block shows, if untouched for 10 minutes (undo / a block being added). PAGE_LIST cover_url
     falls back to the first drawing preview; activity verb "Drew" for whiteboard pages.
   - Web: core/journal/DrawingCanvas.jsx (lazy; overlay with Done, or embedded with Full screen;
     saves 1.2 s after a change, a preview at most every 10 s and on leaving / tab hidden; files
     sent once each). **Gotcha (data loss, caught by e2e):** never read the scene from the
     Excalidraw API in a save that can run on unmount - the closing canvas is already empty. Keep
     the latest {elements, appState, files} from onChange in a ref and save that.
     Editor.jsx: custom block "drawing" (createReactBlockSpec(...)() ), own "/" menu
     (slashMenu={false} + SuggestionMenuController with getDefaultReactSlashMenuItems + "Drawing").
     JournalList "+ Whiteboard" + Whiteboard pill; Home quick action "Whiteboard" (8 actions).
   - Fonts: scripts/copy-excalidraw-fonts.js (npm run build) copies node_modules fonts to
     web/public/fonts (git-ignored, docker-ignored); web/public/excalidraw-assets.js (a plain
     <script> in index.html) sets window.EXCALIDRAW_ASSET_PATH='/'. Excalidraw always lists esm.sh
     as a backup source and Chrome logs a CSP error for a blocked backup even though it loads ours
     first - so font-src also allows https://esm.sh (used only if our copy is missing).
   - npm overrides in web/package.json for Excalidraw's sub-dependencies (katex 0.19.0, lodash-es
     4.18.1, nanoid 3.3.20 / 5.1.16). Left: braces (no fixed version exists; only in sass's
     build-time file watcher, never in the browser or the server).
   - Tests: 256 API (test_drawings.py), 56 browser steps (whiteboard: draws with the mouse, full
     screen, checks both strokes are saved; / Drawing sketch block).
3zb. **Dev on the tablet; handwriting -> text** (2026-10-14).
   - The Tab S7 couldn't reach dev (ERR_CONNECTION_TIMED_OUT): Wi-Fi is a Private network, Docker's
     allow rules are Public-only, and only 8080 had a rule. Added firewall rule "Off the Clock dev
     web (8081)" (TCP 8081, RemoteAddress LocalSubnet, Profile Private) via an elevated prompt the
     user approved (pass the command with -EncodedCommand; -Command lost its quotes). Neither
     rule covers Tailscale (100.64.0.0/10) yet.
   - reMarkable-style "write and it becomes text" in journal pages: Samsung "S Pen to text" works
     straight in the BlockNote editor in **Samsung Internet**; in Chrome the S Pen only brings up
     the keyboard (user tested both). A "pen box" (plain textarea) was built for Chrome, then
     removed once Samsung Internet worked - nothing to build. Converting handwriting ON A CANVAS:
     later, with AI on this PC (docs/ROADMAP.md 5c).
   - Writing mode: JournalPage "Full screen" (notes pages) adds body.writing-mode (hides sidebar /
     navbar / tabbar, wide page, 1.45rem lines, 40dvh blank space below) + requestFullscreen; leaving
     browser full screen or Esc ends it. @media (pointer: coarse): bigger journal lines anyway.
     57 browser steps (writing_mode).
3zc. **Mood replaces the page icon** - DONE in dev (2026-10-14). User asked what the 🙂 was (a
   Notion-style page icon placeholder, never set on prod) and chose: replace the icon with a mood,
   5 faces + a word or two.
   - 25_mood.sql: journal_pages.mood (great/good/okay/meh/rough, NULL = not set; MOODS in db.py),
     mood_words TEXT[] (tidy_words: lower case, no repeats, <= 5 of <= 24 letters); icon DROPPED.
   - API: PageIn/PagePatch mood + mood_words; GET /api/journal?mood=; q also searches mood words;
     GET /api/journal/moods?start&end (journal.moods_between: per day, the latest-edited page with
     a mood); /api/calendar also returns `moods`; to-dos carry mood instead of icon.
   - Web: core/journal/moods.js (faces, tones, MOOD_WORDS, pageFace), MoodPicker.jsx (face button ->
     panel: 5 moods, word chips, your own word; saves on tap). Journal list: face thumbnails, mood
     line "Good · proud", mood filter chips. Home journal card: Your week (7 days). Calendar: face
     in the day cell, "Felt good" in the day detail.
   - e2e browsers now run with timezone_id Australia/Brisbane (the container is UTC; "today" in the
     browser must match the day the API dates pages by). Gotcha: never rewrite walkthrough.py with
     PowerShell Get-Content/Set-Content - 5.1 reads it as ANSI and garbles every · and –.
   - Tests: 259 API (test_mood.py), 58 browser steps (mood).
   - Journal list: a kind pill in each card's corner (teal Journal / purple Whiteboard, KIND_PILL),
     and Group by Day (default; "Today", "Yesterday", "Monday 12 October", with the day's mood
     pill from its latest-edited page with a mood) or Month; remembered in localStorage
     offtheclock.journalGroups. Fixed: the volleyball video form remounted (key=games.length)
     when the games list arrived, wiping a title typed before it loaded.
3zd. **Video games (Steam 100% dashboard)** - DONE in dev (2026-10-14). User tracks 100% completions on
   steamhunters.com (not bot friendly - never scrape it) and wanted their own dashboard. Uses the
   official Steam Web API; key is in BOTH .env files as STEAM_API_KEY (passed to the api container by
   docker-compose; never print it, never commit it; the user pasted it into the chat once).
   The user's profile is set in the app (vg_sync), not written here: this repo is public. First full
   sync: ~200 games in ~4 minutes.
   - 26_videogames.sql: vg_games (app_id PK, playtime, last_played, has_achievements NULL = not read,
     totals, completed_at = last unlock once 100%, hidden, synced_at, rarity_synced_at),
     vg_achievements (PK app_id + api_name; name/description/icons from the schema, global_percent,
     achieved, unlocked_at), vg_sync (one row: profile, steam_id, persona_name, last_sync_at,
     last_full_at, last_error). journal_links kinds + 'videogame'.
   - api/app/steam.py: resolve (vanity name / id / profile URL), persona, owned_games (private ->
     friendly SteamError), player_achievements (NoStats for games without), schema,
     global_percentages (no key). Errors never contain the key. PAUSE 0.15 s between calls.
   - videogames.py: run_sync reads every game the first time / with full=true, otherwise only
     games whose rtime_last_played moved or that were never read; schema re-read when the count of
     achievements changes; rarity weekly. Background via BackgroundTasks (routes) or a thread (the
     daily loop started in main.py's lifespan when STEAM_API_KEY is set: checks hourly, syncs if
     >20 h). SYNC dict = progress, polled by the UI every 2 s while running.
   - Activity: "Unlocked" (one row per game per day: the achievement's name, or "N achievements")
     and "Perfected" (completed_at); photo = Steam header image. Tests: conftest's autouse
     no_real_steam makes any real Steam call fail; test_videogames.py fakes steam.py.
   - Web modules/videogames: Dashboard (SyncBar, SteamSetup, tiles, Closest to 100%, Recently
     unlocked, Rarest you have, Latest 100%), Games (show filter, search, sort), VideoGamePanel
     (header, bar, achievements All / Unlocked / Still to get, rarity pills: <=5% orange, <=20%
     purple; Store page and Steam achievements links; Hide). Home tiles: Games at 100%, Achievements.
   - Tests: 267 API, 59 browser steps (video_games: dashboard or the connect form, games list).
   - Pictures: the fixed cdn .../steam/apps/<id>/header.jpg 404s for newer games (17 of 208), which
     use per-game hashed paths. 27_videogame_pictures.sql vg_games.header_url (NULL = not looked up,
     '' = store has none); steam.header_pictures() asks IStoreBrowseService/GetItems (official, key,
     50 ids per call, include_assets) -> shared.akamai.steamstatic.com/store_item_assets/ +
     asset_url_format with ${FILENAME} = assets.header (shared.cloudflare 301-redirects; akamai /
     fastly answer 200). Looked up for games without one on every sync, all of them on a full
     sync. with_pictures() falls back to the old address; GamePicture (steam.jsx) shows a gamepad
     if an image fails. Activity uses header_url too. Result: 207/208 load (the last is a test
     server app with no picture anywhere). 269 API tests.
   - **Profile completion** (user's goal: 50%). CHANGED by the user the same day: only **started games**
     count (at least one achievement unlocked): achievements unlocked / every achievement in those
     (not hidden) games = summary.started_achievements_total - NOT the average per-game % (that's the
     "average" tile). Starting a new game adds its achievements, so the % can drop. First version
     counted every owned game (20.4%); started-only gave 31.8% (2,683 of 8,440 in 128 games). summary.goal = goal_progress(): percent,
     goal_percent (settings key vg_goal_percent, default 50; PUT /api/videogames/goal {percent 1-100}),
     target, needed, reached, days_at_pace (needed / last-30-days unlocks). GoalCard first on the
     dashboard (bar with the goal marked, "N more to reach 50%", "about 2 years 3 months to go",
     change goal inline); Home tile "Profile completion". 271 API tests.
   - Matching SteamHunters (user's figures: 133 started, 23 completed, 2,899 achievements, avg
     38.669%): GetOwnedGames hides "unvetted" apps unless skip_unvetted_apps=0 (3 games: HoloCure -
     Save the Fans!, two Travellin Cats). After: 131 / 22 / 2,897 / 38.2%. The last 2 games are
     probably ones no longer owned (refunds / free weekends): the owned-games API can't list them.
     Playtime already matched (149,987 min ~ 104 days).
   - Stats page (/videogames/stats; GET /api/videogames/stats?months=24): unlocks per month
     (generate_series, zeros kept), rarity bands (RARITY_BANDS), started games by completion
     (COMPLETION_BANDS), most played (top 10). components/charts.jsx: ColumnChart / BarList in plain
     HTML+CSS, one series in --tint (validated with the dataviz skill's validate_palette.js: passes
     light #2563eb on #fff and dark #3b82f6 on #111a2c), <= 24px columns, 4px tops, 2px gaps,
     hairline grid, hover/focus tooltip, values on caps only for few columns (else the highest),
     "Show as a table" for every chart. 272 API tests, 59 browser steps.
   - Profile completion now shows BOTH (user's choice): the big number = AVERAGE completion of
     started games (SteamHunters' "avg completion"; the goal tracks it), the TOTAL (achievements /
     achievements in those games) on a line underneath with why they differ (a 2/2 game counts as
     much as a 20/641 one in the average). goal_progress(games, unlocked_last_30_days, goal):
     points_to_go, plan = quickest route (100% the started games with fewest achievements left
     until the average reaches the goal: games + achievements), days_at_pace from those
     achievements. Live: 38.2% avg, 33.2% total, 11.8 points, 31 games / 445 achievements.
   - **Games added by hand** (28_videogame_extra.sql vg_games.extra): the user's missing game was
     Counter-Strike 2 (app 730, 1/1): GetPlayerAchievements has it, but GetOwnedGames returns
     game_count 0 even with appids_filter (free game). POST /api/videogames/extra {game: store link /
     app id} (steam.app_id_from; refuses no-stats and none-unlocked games; name + picture from
     steam.store_items, which header_pictures now wraps), DELETE /api/videogames/extra/{id} (only
     extras - library games can only be hidden). Extras are re-read on every sync. Games page
     "+ Add a game"; "Added" pill; panel note + Remove. After adding CS2: 23 completed and 38.7%
     average (both match SteamHunters); one more 1-achievement game is still unknown. 275 API tests.
     (The user found it: an old demo they DON'T want counted - leave it out.)
   - **How other players did** (user's choice "Both"): SteamHunters' web pages are behind a Cloudflare
     bot check (even robots.txt), but its public JSON API https://steamhunters.com/api/apps/<id>
     answers plain requests (used by their MIT browser extension): medianCompletionTime /
     fastestCompletionTime (minutes to 100%), playersPerfectedCount / playersStartedCount, points.
     No published terms/limits -> api/app/steamhunters.py: started games only, 1 request/s,
     identifying User-Agent; videogames.sync_community() after the Steam part of every sync: games
     just read, never read, or >7 days old (all on full sync); 404 = unknown but marked read; if
     SteamHunters fails the Steam sync still counts and the note says so. 29_videogame_community.sql
     vg_games.sh_* columns. GAME_SELECT adds perfect_rate and Steam's cross-check rarest_percent
     (min global_percent: no more players than that can have 100%'d it). SteamSpy was checked and
     rejected: bot-friendly, but median_forever is now 0 (Steam stopped sharing playtime).
     UI: panel "Compared with other players" (you / median / fastest bars, "you've played 93% of the
     median", "33.3% of players who started it have 100%'d it", cross-check), list meta + sorts
     "Rarest to 100%" / "Quickest to 100% (median)", Latest 100% cards show the rate.
     BEFORE_GOING_PUBLIC row: ask SteamHunters first. 278 API tests, 59 browser steps.
   - Readability pass (user asked for icons: trophy for the 100% rate, a bell curve for the median, and
     a better layout on PC): Games is now GameTable - on a PC a table (picture 120px, name + 100% pill
     + last played, progress "56 / 76 · 73.7%" with bar, then ClockIcon your time / BellCurveIcon
     median / TrophyIcon 100% rate) with clickable sort headings and an icon key above; <= 900px each
     game is a card with the three stats as an even row of chips (.game-stats is display: contents on a
     PC, a 3-column grid on phones). Panel "Compared with other players": four icon tiles (Your time,
     Median, Fastest = HourglassIcon, 100% rate) + coloured time bars. New icons BellCurveIcon,
     HourglassIcon (a first bell curve looked like a warning triangle at 14px - redrawn softer).
   - Pinned header (user: search, filters and the headings should "float" while scrolling, so the
     icons needn't repeat): .games-pinned (sticky, top = 56px nav bar + safe area, page background)
     holds the toolbar, the show-chips and GameHead; GameTable is now just the rows. Above 900px the
     rows show plain numbers (icons only in the headings, no key); <= 900px cards keep icon chips and
     the key; <= 700px the block isn't pinned (it would cover half a phone screen). The e2e scrolls
     3000px and checks the search box is still near the top.
   - Games toolbar also has "Sync now" (steam.jsx SyncButton: quick sync, shows "Syncing 12 of 40..." while
     running, list reloads when done; tooltip = last synced). Full sync stays on the dashboard.
   - **DLC split** (user: SteamHunters splits main game and DLC in each game's achievements). Desk review
     2026-10-14: Steam's API and store data don't say which achievements are DLC; SteamHunters' groups
     (/api/apps/<id>/updates) need a login; the SteamDB extension's groups come from a private SteamDB
     endpoint fed by SteamHunters (not for us); TrueSteamAchievements has no API; completionist.me 403s.
     **Exophase** works: plain-HTML game pages with an h3.dlc-add-on per DLC, robots.txt only blocks
     /search, terms silent on automated access. 30_videogame_dlc.sql: vg_achievements.dlc (NULL = main
     game), vg_games.sh_has_dlc (SteamHunters' hasPaidDlc), exo_url ('' = none found), exo_synced_at.
     exophase.py: candidates() via api.exophase.com/public/archive/games?q= (Steam entries, same name
     first, ™ dropped), the page must link to store.steampowered.com/app/<id>, parse() ul.achievement
     lists, names matched by key() (case / punctuation / accents ignored). videogames.sync_dlc after
     sync_community: started, not hidden, sh_has_dlc not false, exo_synced_at NULL (reset when the
     schema is re-read) or full sync; 2 s pause. Panel: "Main game 40 of 50 · <DLC> 3 of 12" line,
     Main game fold (open) + one fold per DLC with count and bar; filters work inside. Tests use a
     made-up page in Exophase's layout (no copied page).
   - **Free updates aren't DLC**: Exophase heads free content updates ("Update #1", "Commander Mode")
     exactly like paid DLC (same markup). A section only counts as DLC if exophase.is_dlc() matches it
     to one of the game's real DLCs from SteamHunters' public /api/apps/<id>/related (typeString DLC,
     steamhunters.dlc_names); other sections stay with the main game (they count for its 100%).
     dlc_name() trims the game / series name ("Far Cry® 5 - ...", "Just Cause™ 3 DLC: ...",
     "Fallout 4 Far Harbor", "The Binding of Isaac: Afterbirth"); key() drops ™ ® ©.
   - Both readers retry once 5 s after a timeout (SteamHunters was briefly slow twice in a row).
   - GAME_SELECT: dlc_count / dlc_achievements / dlc_done (LATERAL with rarest_percent); the Games
     list shows a purple "DLC" pill with a PuzzleIcon (DlcBadge; tooltip "2 DLCs with achievements:
     3 of 12"). Dev result: 40 games with DLC, all found on Exophase (e.g. Dead by Daylight 46 DLCs).
   - Tests: 283 API, 59 browser steps (video_games opens the game with the most DLCs).
3ze. **Check-over: speed, dead code** (2026-10-14). Every GET endpoint < 80 ms on dev data (timing
   script + a read-only Playwright page tour: no page repeats a request; pages settle ~0.7 s; Games
   list shows rows at 0.6 s, the rest is Steam's CDN with lazy images). Cached lookups 4-14 ms.
   Entry bundle 456 KB (135 KB gz); Excalidraw / BlockNote / mermaid chunks load lazily.
   Removed BoardIcon, .game-list / .time-value CSS, 12 needless exports; /api/videogames list leaves
   out sync bookkeeping (LIST_LEAVES_OUT; the game's own endpoint has everything). vite 6.3.5 ->
   6.4.4 (dev-server advisories). pip-audit clean; npm audit = only the known braces chain (sass's
   watcher inside Excalidraw, build time only). ESLint: the same 3 deliberate warnings.
   Async routes (photo uploads, Tamiya / Hasegawa / Bandai lookups, scan) do short blocking DB calls
   on the event loop - fine for one user; would matter with many.
3zf. **7-day changes** (user liked SteamHunters' "+7 since last week"). summary.week = week_change():
   achievements / perfect / in_progress / percent (average) / total_percent, now minus 7 days ago -
   worked out from unlock dates (done_then = unlocked before now() - 7 days), so no snapshot table.
   core/Stat.jsx `change` prop + Change component (.delta pill: green up, amber down, grey 0; the
   old `.change` class belongs to stock history). Dashboard tiles + GoalCard (average and total) and
   the Home tiles. First dev numbers: +59 achievements, +3 at 100%, -2 in progress, +0.8% average.
   284 API tests.
3zg. **Calendar, unobtainable, quick wins, recap** (2026-10-14; user picked 4 of 7 ideas from a review
   against SteamHunters / completionist.me / Exophase / TSA / Playnite / HLTB / Backloggd. Not picked:
   hunting list, play status, guides link; rejected: points, session history, friends, HLTB).
   - 31_videogame_unobtainable.sql: vg_games.sh_unobtainable (SteamHunters' unobtainableAchievementCount),
     vg_achievements.unobtainable. sync_community asks /api/apps/<id>/achievements (obtainability 3 =
     unobtainable, keyed by Steam apiName) ONLY when the count > 0. videogames.recount() (shared with
     sync_game): achievements_total leaves out unobtainable ones you don't have, so 100% without them.
     Panel: "N can't be earned any more" + Unobtainable pill; DLC group totals exclude them.
     Example found: Hitman Absolution 8; the user's CoD Infinite Warfare 1.
   - summary.quick_wins: started, SteamHunters median known; minutes_left = median x left / total
     (rough), fewest first. summary.streak / stats.streak = streaks(days, today): current (alive till
     today ends), longest + end day. Dashboard: Quick wins card, StreakPill on Recently unlocked.
   - Stats page: Recap (GET /api/videogames/recap?month=YYYY-MM: achievements, games, previous - same
     days of the month before while the month is running -, best_day, rarest 3, top_games 5, perfect,
     first, this_month; month arrows) + UnlockCalendar (53 weeks x 7, Monday first, levels = own
     quartiles, --heat-1..4 ramps checked with the dataviz validator: adjacent dE >= 14.5; hover shows
     the count, "Show as a table"). Dates use the DB's Brisbane timezone (SHOW timezone).
   - GOTCHA: plain `dev.ps1` does NOT run migrate.ps1 (only -Refresh does) - run .\migrate.ps1 after
     adding a db/init file, or the API fails with UndefinedColumn (a dev sync did).
   - Tests: 288 API, 59 browser steps (stats: recap arrows, 53 calendar weeks; Quick wins card).
3zh. **Epic + Ubisoft, faster full sync** (2026-10-14).
   - Ubisoft research: Ubisoft has NO public API; Exophase only sees Ubisoft Connect *challenges* (its
     "achievements" URL for a Ubisoft game 302s to /challenges/; 9 of the user's 13 Ubisoft games are
     0/0 there; Siege 0/34 challenges vs the user's real 45/48 achievements + ~850 h). The Ubisoft
     launcher's local cache (checked with the user's permission, token-like values hidden) holds only
     the store catalogue, settings and its own code - progress is fetched live via their private
     GraphQL and never stored. Logging in to Ubisoft's private API with the user's password: rejected.
     => Ubisoft achievements are TYPED IN; names / pictures / playtime come from Exophase.
     Exophase per-player earned list: api.exophase.com/public/player/<pid>/game/<master_id>/earned
     (used once for a one-off Excel dump of Ubisoft challenges in the user's Downloads; not in the app).
   - 32_videogame_platforms.sql: vg_sync.exo_profile / exo_players {"epic": pid, "uplay": pid} /
     exo_synced_at / exo_error; vg_other_games (platform epic|ubisoft, source_id = Exophase master id
     or NULL = added by hand, exo_done/total/minutes, my_done/total/minutes typed in, hidden).
     othergames.py: SELECT works out done/total (Ubisoft = my_*, Epic = my_* else exo_*), playtime
     (my else exo), challenges_* for Ubisoft; routes GET/PUT /videogames/other/account (account field
     `linked`, not `platforms` - it's merged with the games reply), GET/POST /videogames/other,
     PATCH/DELETE /videogames/other/{id} (Exophase games can only be hidden). Router included BEFORE
     videogames (else /videogames/{app_id} swallows /videogames/other). sync_other() runs on the
     Exophase side of every sync. The user's profile lives in the DB only (public repo).
   - Web OtherPlatforms.jsx: GamesPage = PlatformSwitch (Steam / Epic / Ubisoft, only platforms you
     have) + Steam GamesView or OtherGamesView (?platform=epic|ubisoft); OtherGamePanel ('othergame'
     panel; Ubisoft form: achievements you have / in the game / hours); OtherPlatformsCard on the
     dashboard (or the Exophase connect form). Steam numbers stay Steam-only.
   - Faster full sync: Steam games 4 at a time (ThreadPoolExecutor, STEAM_AT_ONCE); then
     sync_others(): SteamHunters and Exophase side by side (different sites); each site's _get is
     _spaced() (one request at a time, PAUSE apart, across threads); DB writes of the two sides take
     turns (_writes lock - without it the two transactions DEADLOCKED on the same game, caught by
     tests); progress counted with step() under the lock. A full sync skips SteamHunters numbers
     < 1 day old (FRESH) and DLC lists < 30 days old (DLC_EVERY). The DLC side does games known to
     have DLC first, then waits for SteamHunters (Event) before games it hadn't judged - otherwise a
     first sync would ask Exophase about every started game.
   - Tests: 293 API.
3zi. **Epic / Ubisoft look like Steam: full achievement lists** (2026-10-14). User: list every Ubisoft
   achievement ("should be the same as Steam") and make Epic / Ubisoft look the same as Steam.
   - 33_videogame_other_achievements.sql: vg_other_games.steam_app_id / steam_checked_at / header_url /
     list_synced_at / list_done / sh_* ; vg_other_achievements (game_id, api_name, name, description,
     icon, icon_gray, hidden, global_percent, achieved, unlocked_at, sort_order).
   - Steam version by name: steam.find_app (Steam store search JSON; exact match ignoring case,
     punctuation, TM/(R), "Tom Clancy's"; drops up to 2 words from the end - "Rainbow Six Siege X" ->
     359550, 48 achievements = the user's 48). 18 of 20 matched; Rocket League isn't sold on Steam.
     Fix a match in the panel ("Not the right game?": store link / "Not on Steam").
   - Lists: Epic = exophase.game_awards(page) + exophase.earned(player, master_id) (dates; rarity =
     Exophase players), re-read when the earned count changes (list_done); Ubisoft = Steam schema +
     global % of the Steam version, ticked by the user (PUT .../achievements/{api_name}, PUT
     .../achievements = tick all), weekly refresh keeps ticks (save_list keep_ticks). done/total come
     from the list when there is one, else Epic's Exophase counts / Ubisoft's typed numbers.
   - API shape = Steam game's (app_id "epic-12" / "ubisoft-12", achievements_done/total, percent,
     header_url = the Steam version's picture, sh_* / perfect_rate from SteamHunters for the Steam
     version, rarest_percent), so the SAME GameTable / GamesView (platform switch; OTHER_SHOWS filters
     client-side) and VideoGamePanel (id string -> other game: tick buttons, Tick all, hours, Steam
     version box, Exophase link; no journal mentions yet) are used. OtherGamesView / OtherGamePanel gone.
   - conftest refuses steam.find_app (it uses httpx directly, not steam._get). Tests: 295 API.
   - Bugs found in dev: find_app's word-dropping range made NO search for one-word names
     (Supraland) - now whole name first, then drop up to 2 words but keep >= 2. The tick buttons got
     the paint checklist's `.tick` (position: absolute, under the icon) - renamed `.ach-tick`.
     LESSON: grep styles.css for a class name before using it (.change, .tick both clashed).
   - Epic playtime: no source (Exophase blank for Epic; Epic has no public API; Heroic / Legendary use
     the user's Epic login) -> the panel's "Hours played" box shows for Epic and Ubisoft.
4. ~~Excel reads via Power Query~~ - dropped
5. ~~Excel writes via VBA buttons~~ - dropped
6. MCP server whose tools call the API (port 8000), so Claude can answer "what am I low on?"
   and update stock

DBeaver connection confirmed working (2026-10-11).

## Current state
- Folder: `C:\Users\xdhar\hobby-inventory`
- `docker-compose.yml`: service `db`, image `hobby-inventory-db:1.0`, container
  `hobby-inventory-db`, volume `hobby_pgdata`, port `127.0.0.1:5433 -> 5432`,
  pg_isready healthcheck, `restart: unless-stopped`
- `db/Dockerfile`: postgres:17-alpine, `TZ=Australia/Brisbane`, copies `db/init/`
- `db/init/01_schema.sql`: lookup tables `categories`, `brands`, `storage_locations`;
  table `supplies` (CHECK lists for paint_type/finish/condition, qty_on_hand >= 0,
  UNIQUE(brand_id, product_code), updated_at trigger); view `v_supplies`
  (names, `item_ref` SUP-0001, `stock_status` Out/Low/OK, `total_value`)
- `db/init/02_seed.sql`: lookup values only (20 categories, 4 brands, 7 locations). No supplies.
- `db/init/03_wishlist.sql`: **idempotent migration** (IF NOT EXISTS), also applied by hand to
  the live DB on 2026-10-11. Tables `wishlist` (UNIQUE brand+code, priority High/Normal/Low,
  got_it flag, updated_at trigger) and `product_info` (scraped title/series/description +
  photo as BYTEA, UNIQUE brand+code, cascade-deletes with brand). Pattern for future schema
  changes: new numbered idempotent file in db/init, `pg_dump` backup, then pipe into psql.
- `backups/` (git-ignored): `pg_dump --clean --if-exists` files.
- `scripts/import_spreadsheet.py`: reads the **Supplies** and **Lists** sheets of
  `C:\Users\xdhar\Downloads\Hobby_Supplies_Inventory.xlsx`; adds missing categories/brands
  (it added Milliput, Microscale); upserts on (brand, product_code); keeps SUP-#### numbers as
  supply_id and resets the SERIAL sequence; one transaction; applies `FINISH_FIXES`
  (XF-64/76/71 -> Flat / Matt, X-10 Gun Metal -> Metallic). Other sheets (Summary, FMP) ignored.
- `api/`: FastAPI, one module per part of the app (see main.py's docstring and 3p): supplies,
  wishlist, products, catalog, models, build, colours, paints, spending, settings, lookups,
  images; shared db.py (connection, enum lists that must match the SQL CHECKs, friendly
  CONSTRAINT_MESSAGES, insert_row / update_row / found helpers); tamiya.py / hasegawa.py
  (scrapers: httpx + BeautifulSoup; Tamiya pages are Shift_JIS -> decode cp932). Connects to
  `db:5432` inside the Docker network. psycopg_pool ConnectionPool (see 3z).
  Docs at `/api/docs`. Routes all start with `/api` so nginx can forward them unchanged.
  The api container mounts ./backups at /backups (Settings > Backups) and has pg_dump 17.
- `web/`: React 19 + Vite 6, multi-stage Dockerfile (node build -> nginx). `nginx.conf` proxies
  `/api/` to `api:8000` via Docker DNS (resolver 127.0.0.11), so no CORS is needed.
  `src/api.js` = all fetch calls (grouped by area) + small formatters (money, duration,
  shortDate, today). App = nav bar, tabs (tab bar on phones), panels, toast, timer banner.
  Pages: InventoryView, WishlistView, ModelsView, ColoursView. Panels (Drawer): ItemPanel,
  AddPanel, WishForm, ShopPanel, ModelPanel (ModelForm, PaintChecklist, KitPaintsPicker,
  TimeTracker, BuildLog), SettingsPanel (Spending, PriceGuide, ListsManager). Shared: Fold,
  ColourMatches, ScanButton, PhotoUpload, SimilarItems, StockHistory, OwnedBadge, Elapsed, icons.
  Last shop typed is remembered in localStorage; otherwise the default shop setting is used.
  `package-lock.json` was generated in a node:22-alpine container (no Node on the host).
- New-supply form defaults to the user's conventions: qty 1, reorder 0, Sealed, today, location Other.
- `.venv` (git-ignored) with `requirements.txt`: openpyxl, psycopg[binary] (import script only)
- `.env` (git-ignored) holds DB name/user/password/port; `.env.example` is the template
- `start.ps1`: checks Docker, `docker compose up -d --build`, waits for healthy, prints details
- Port 5433 chosen because a stopped, unrelated `councils-postgres-1` container claims 5432.

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
