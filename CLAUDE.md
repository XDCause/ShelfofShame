# Shelf of Shame - project notes for Claude

**Project name: "Shelf of Shame"** (renamed from "Hobby Inventory" on 2026-10-11).
GitHub: https://github.com/XDCause/ShelfofShame (PUBLIC - never commit .env, backups, or
copied third-party pages). The user-visible name changed (app title, docs, API title,
scraper User-Agents); internal names were deliberately KEPT to avoid migrating data: folder
`hobby-inventory`, containers `hobby-inventory-*`, volume `hobby_pgdata`, database
`hobby_inventory`, user `hobby`, localStorage key `hobby-inventory.lastShop`.
Git author: XDCause <121413369+XDCause@users.noreply.github.com> (GitHub no-reply address, so
the user's real email isn't published in commits).

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
     (search only - the e2e never fetches tamiya.com; thumbnails are blank in its screenshots).
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
  `db:5432` inside the Docker network. One connection per request, no pool (fine at this scale).
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
