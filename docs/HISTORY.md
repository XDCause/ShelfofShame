# Off the Clock - build history

Everything built so far, in order, with the reasons and the lessons at the time (moved out of CLAUDE.md
on 2026-10-16 so the notes Claude reads first stay short). Numbers match the old CLAUDE.md sections, so
"see 3zh" still finds the right place. Newest at the bottom.

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
3zj. **Chess** (2026-10-14). User chose all four: ratings dashboard, games + board replay, openings,
   over-the-board games. chess.com's official public API (no login, just the username).
   - 34_chess.sql: chess_account (one row: username, profile, stats JSONB, last_sync_at/error),
     chess_archives (month, games, complete = month over when read), chess_games (source chesscom |
     otb, uuid UNIQUE, played_at, time_class bullet/blitz/rapid/daily/classical, colour, my/opp rating,
     result win/loss/draw from your side + how, eco/opening/opening_family, pgn, moves, accuracy).
     journal_links kinds + 'chess'.
   - chesscom.py: profile / stats / archives / month; game_row() (your side; DRAWS set; opening name
     from chess.com's ECOUrl slug, moves dropped; family_of = up to Opening/Defense/Gambit/Game/...);
     username_from (lower case, 3-25 chars). Requests one at a time (PAUSE 0.5).
   - chess.py: background sync (SYNC dict, polled) - profile + stats, then months not complete (all on
     full); daily loop started in main.py's lifespan (always; waits for a username). summary (classes
     from stats with week_change = rating now - last rated game before 7 days ago; puzzles; week W/L/D;
     recent), ratings (last rating per day per class), games (filters, rating_change via lag()),
     openings (families + variations: games, W/D/L, score = (W + D/2) / games), OTB add / patch /
     delete (online games: notes only).
   - Activity: one row per day per time control for online games ("Blitz chess: 12 games · 7-4-1"),
     each OTB game; so they show on the calendar. Journal: mention kind 'chess', mentionable search.
   - Web modules/chess: manifest (Dashboard / Games / Openings; panel chessgame; Home tile; quick
     action "Log a chess game" - Home now passes `navigate` to module actions), ChessViews.jsx,
     chessParts.jsx (ResultPill, RatingChange, timeControl, OtbForm, useChessAccount, ChessSetup,
     ChessSyncBar), ChessGamePanel.jsx, Board.jsx (chess.js 1.4.0 dynamic import; own CSS board,
     unicode pieces sized with cqw; flipped for Black; arrows / buttons / move list). charts.jsx
     LineChart (fitted axis, crosshair tooltip, table view). ChessIcon (a knight).
   - Tests: 300 API (test_chess.py, fake chess.com), 60 browser steps (chess: OTB game with PGN,
     replay, openings). e2e counts: 9 quick actions, 5 hobby cards.
   - **LESSON (data loss in dev):** run_e2e.ps1 restores dev's data from the backup taken at its START,
     so anything the user does in dev WHILE it runs is lost (the user connected chess.com mid-run and
     it was wiped). Tell the user before every e2e run in dev.
3zk. **Dashboard counts every platform** (2026-10-14; user: the dashboard only showed Steam). summary /
   stats / recap take ?platforms=steam,epic,ubisoft (default all; 422 for none). videogames.ALL_GAMES /
   ALL_ACHIEVEMENTS = UNION of Steam and othergames.SELECT / vg_other_achievements (app_id as text;
   steam_ids() turns Steam's back into ints); games_where() runs GAME_SELECT and othergames.SELECT with
   the same WHERE and merges. summary.available = platforms you have games on. Web: PlatformToggles
   ("Counting  Steam Epic Ubisoft", the last one can't be turned off; "matches SteamHunters" when Steam
   alone) on Dashboard and Stats, shared via useCounting() (module store; a reload = all again). Home
   tiles count all. Ubisoft ticks have no date: they count in totals, never as "this week" or the calendar.
   Tests: 301 API, 60 browser steps.
3zl. **Reading** (2026-10-14). User chose all four: progress + reading log, yearly goal + stats, ISBN
   scan, ratings / reviews / quotes; plus a Goodreads import. Open Library (no key) for book data.
   - 35_reading.sql: books (title, author, isbn 13, ol_work, cover_id, pages, year, genres TEXT[], format
     paper/ebook/audio, status want/reading/finished/dnf, current_page, started_on, finished_on, rating 1-5,
     review, goodreads_id UNIQUE, looked_up_at), reading_log (page reached + pages since the last update,
     logged_on, minutes), book_quotes. Goal = settings reading_goal_<year>. journal_links + 'book'.
   - openlibrary.py: search.json (q / isbn / title+author), isbn13() (ISBN-10 -> 13, check digits),
     genres_of() (subjects -> up to 3 plain genres; a matched genre's words are removed so "science
     fiction" isn't also Science), covers hot-linked from covers.openlibrary.org by cover id.
   - reading.py: lookup, books (shelves, search, sorts), progress (want -> reading, started_on; at_the_end),
     finishing a logged book logs the rest of its pages that day; pages_read = log + never-logged
     finished books (their whole length on the finish day); summary (reading now, goal + on pace,
     streak via videogames.streaks), stats, quotes, Goodreads CSV import (Exclusive Shelf -> status,
     dnf-like shelf names -> dnf; re-import updates shelf / rating / date read / review only), then a
     background cover look-up (COVERS state, 1 request/s). Activity: Read (per book per day), Started
     reading, Finished / Stopped reading - so the calendar shows them.
   - Web modules/reading: Dashboard (goal card, tiles, reading-now cards with a page box, recently
     finished, up next), Books (shelf chips, search, sort, grid, Goodreads import fold), Stats (Reading
     calendar = the video games UnlockCalendar, now exported with title / one / many props; charts),
     Quotes; panels book (BookPanel) and addbook (search / Scan ISBN / type it in). BookIcon, QuoteIcon.
   - Tests: 308 API (test_reading.py, fake Open Library), 61 browser steps (reading; Home counts:
     10 quick actions, 6 hobby cards, tiles + READING).
3zm. **Complete + skipped steps, photo badges, camera** (2026-10-14).
   - Every hobby's steps end with "Complete" (db.STAGES; 36_build_complete.sql CHECK). models.skipped_steps
     TEXT[]: steps passed over (snap-fit HG Gunpla: Built -> Complete). models.build_steps() rules: moving
     the stage ahead skips the steps between (never the first, Built); back forgets skips after it;
     skipped_steps sent alone toggle skipped <-> done (only between Built and the stage); Complete =>
     Finished; status Finished => Complete; leaving Complete / Finished goes back to the last step really
     done and In progress. Old Finished kits got Complete with the steps after their last tick skipped.
     BuildSteps: tap ahead = jump (toast says how many skipped), last ticked = untick, earlier = toggle
     skipped; skipped = dashed dot "· skipped"; StepBar .skip; card text "Complete (3 skipped)".
   - Badges over card photos (kits, board games, gear) were see-through tints (the s-* / tone colours
     came later in the CSS than the white "on photo" rule). Now solid fixed colours, white text, white
     ring + shadow (end of styles.css, !important over the tints).
   - components/PhotoPick.jsx: touch screens ((pointer: coarse)) get Take photo (capture=environment) +
     Gallery; computers one button. Used by BuildLog, PhotoUpload, RowPhoto (RecordFields). Inputs carry
     data-source=camera|gallery (the e2e uses gallery). Journal images still use BlockNote's own picker.
   - Tests: 308 API, 61 browser steps (gundam: Built -> Complete skips 3; phone: Take photo / Gallery).
   - **Several photos per build-log entry**: 37_log_photos.sql model_log_photos (photo_id, entry_id CASCADE,
     photo, photo_type); the old model_log.photo / photo_type / photo_updated moved there and were
     dropped (rehearsed on a copy of prod: 6 photos, identical bytes). Entries carry `photos` (ids);
     POST /model-log/{id}/photos (one per request, 30 max -> 409), GET / DELETE /model-log-photos/{photo_id}
     (never changes -> cached for good, URL = id). PhotoPick `multiple` (gallery picks several; camera one
     per press, appended). BuildLog: thumbnails with ✕ before saving, a square grid per entry (one photo
     shows bigger), ✕ per photo. Other photo spots stay single (one picture per item).
3zn. **Checklist + build log** (2026-10-14). Each paint you don't have gets "+ Wishlist" on its row (canWish:
   brand + code and not on the wishlist, or a mix missing a part): POST /models/{id}/wishlist?paint_id=
   (one checklist line; 404 if not on the model). "What it's for" boxes are FitTextarea (measured
   scrollHeight, re-measured on a width change) - the old rows = length / 42 guess left a blank line on
   wide screens and cut notes off on phones (seen on the user's Triceratops on prod). Build log: Edit per
   entry (note, day, remove photos, add photos; Save / Cancel); PATCH /model-log/{id} blanks -> NULL text,
   a null day is ignored. Photos are removed in Edit (no ✕ on the plain view). Reload before closing the
   edit form, or the deleted photo is requested once (404 - caught by the e2e's browser errors).
   Tests: 309 API, 61 browser steps.
3zo. **Spent on kits** (2026-10-14): /models/summary `all_kits` (every kit but Wanted: kits, value, unpriced,
   finished, finished_value); Kits card's 4th cell (.stat-grid.four, 2 x 2 on phones). Prod: $56.85, 3 kits.
   **BoardGameGeek** (checked 2026-10-14, not used yet): robots.txt allows game pages (Crawl-delay 5);
   the XML API (xmlapi2) answers 401 without a token - since mid/late 2025 every app must register at
   boardgamegeek.com/applications (approval can take a week+) and send Authorization: Bearer <token>.
   Use that, never scrape pages; a BEFORE_GOING_PUBLIC row is needed if it's ever added.
3zp. **Volleyball teams + defaults** (2026-10-14). 38_volleyball_teams.sql: volleyball_teams (name unique any case,
   location, is_default - one at most, partial unique -, retired, notes); volleyball_games.team_id replaces the
   typed `team` text (names became teams, then the column was dropped). GameIn/Patch take team_id or a team
   name (found any case, else added). GET /volleyball/teams = {teams (games, last_played), defaults {team_id:
   default else last game's team, venue: its location else last venue, kind: last kind}, opponents, venues};
   POST / PATCH (default moves; retiring drops it) / DELETE (409 with games -> retire). Web: "Your teams" card
   on Games (team chips -> vbteam TeamPanel; Delete becomes Retire when it has games); game form: team select,
   Where follows the team unless you typed a new place, datalists vb-opponents / vb-venues, kind starts as
   your last one; a calendar event's location is the venue when logging from it. FormPanel onField +
   deleteLabel. CSV Team column from the join. Tests: 310 API, 61 browser steps.
3zq. **Board games from Wikidata** (REPLACED by Gameology, 3zt) (2026-10-15; BGG needs a registered token, so Wikidata instead - CC0, no
   account). 39_board_game_wikidata.sql: board_games.wikidata_id / bgg_id / designer / min_age.
   wikidata.py: one SPARQL query - EntitySearch (mwapi) for the name, kept to items with a BGG id or an
   instance of board / card / tabletop game; facts P2339 BGG id, P1872/P1873 players, P2047 duration (minute /
   hour units), P577 date, P2899 age, P18 image, P50|P178|P287 designer, P123 publisher. Several editions =
   several rows: widest players, earliest year. Name-only items (a "series") left out. game(qid) picks the
   matching item. Photos: Commons Special:FilePath?width=600 through images.fetched_photo, in a BackgroundTask.
   Routes: GET /board-games/lookup?q= (game_id if you have it), POST /board-games with wikidata_id (fills blanks
   server-side - the browser never sends facts or a photo URL to trust), POST /board-games/{id}/wikidata
   {wikidata_id, replace}. Web: WikidataFind above the add form ("Use" fills the form) and "Fill in from
   Wikidata" in a game's panel; gameMeta shows age + designer. Live: Catan -> 3-4, 75 min, 10+, Klaus Teuber,
   Kosmos, 1995, BGG 13, 180 KB photo. Root isn't findable by name (common word). conftest refuses
   wikidata._query / photo. Tests: 313 API.
3zr. **Volleyball byes** (2026-10-15). 40_volleyball_bye.sql volleyball_games.bye ('win' | 'no result'); a bye clears
   opponent + sets (no_sets_on_a_bye); RESULT: bye win = 'Won' (ladders count it), no result = NULL; summary
   bye_wins ("incl. 1 bye" on the record). Activity: verb "Had", title "Volleyball bye", detail "Counted as a
   win" / "No result". Form: "Played | Bye – win | Bye – no result" (not for Training) hides Against + sets;
   score() / gameTitle() show "Bye – win" / "Bye". Tests: 314 API, 61 browser steps.
3zs. **Volleyball Games page redesign** (2026-10-15; user: 13 games in one narrow column looked bad on a PC).
   .vb-layout: seasons (one card per team: name, "12 social games · 7-4-1 won-lost · location", form dots) with a
   row per game (date | vs opponent, venue only if not the team's, notes / videos | result pill), the season's
   usual kind said once (rows mark exceptions); side column (sticky, 300px) Form (last 10 + run) and Head to
   head (record per opponent, top 8 + All). <=1000px the side cards go below; phones: dots on their own line.
   Prod has "vs BYE 0-0" on 29 Sept (made before byes existed) and venue typo "Aquatice" (12 games + team).
3zt. **Board games from Gameology, not Wikidata** (2026-10-15; user: Wikidata "quite bad"). wikidata.py removed.
   gameology.py: Shopify storefront /search/suggest.json with q = '<name> product_type:"Board Games"' and
   resources[options][fields]=title,product_type (a plain search matched descriptions: "root" -> Magic cards),
   /products/<handle>.js; facts from tags "BGG Min/Max Players", "BGG Min/Max Play Time", "BGG Min Age",
   "BGG Weight" (only 1-5: 0.25 = not rated, 310.25 seen once), "BGG Category/Mechanism/Type"; vendor =
   publisher ("(Self-Published)" dropped); search price in dollars, .js in cents; photos only from
   cdn.shopify.com (?width=600). Ranked: title starts with the words > all words > rest, games before
   expansions, ones with facts first. Sold-out games: unavailable_products=show ("last" pushed them past the
   10 results the store returns, so they never showed); a "Sold out" pill. 41_board_game_shop.sql: weight, categories, mechanisms, shop_handle,
   shop_url, shop_price; wikidata_id dropped. Routes: lookup, POST /board-games {shop_handle}, POST
   /board-games/{id}/shop. Web ShopFind; panel: weight pill ("Medium-light · 2.5/5"), category chips,
   mechanisms, "Gameology $69.95 ↗". No BGG rating / rank in the tags. robots.txt allows product pages;
   agents.md asks for Web Bot Auth for server traffic - noted in BEFORE_GOING_PUBLIC.
3zu. **Volleyball videos are uploads** (2026-10-15; user: "should be upload videos not links"). Files on disk, NOT in
   Postgres: docker-compose api volume `./media:/media` (MEDIA_DIR; each copy has its own; media/ git-ignored).
   42_volleyball_video_files.sql: url nullable; file_name ("<id>-<hex>.<ext>", CHECK), file_type, file_size,
   original_name. PUT /volleyball/videos/{id}/file streams the body to a .part file, checks the type
   (mp4/mov/webm/mkv/3gp/m4v) and the first bytes ("ftyp" at 4, or EBML), 4 GB max, renames into place,
   removes a replaced file; GET .../file = FileResponse (Starlette 1.8 answers Range -> seeking works);
   DELETE removes the file. VIDEO_SELECT file_url = '...file?v=<file_name>' (new name per upload, cached
   immutable). nginx: `location ~ ^/api/volleyball/videos/[0-9]+/file$` 4g, proxy_request_buffering off, 900 s.
   Web: PhotoPick takes accept / cameraLabel / galleryLabel (Record video / Choose video); VideoPanel uploads
   with XMLHttpRequest progress ("Uploading 45% · 120 MB of 260 MB"), deletes the new row if the upload fails,
   player in the panel, "Or add a link" still possible; cards show a frame (`#t=0.5`, preload metadata).
   Backups: backup.ps1 (nightly) robocopies new files media -> backups\media (/E /XC /XN /XO; never deletes) and to -CopyTo\media (3zx). Live test: 300 MB via nginx in 4.4 s, Range 206.
   e2e uploads a tiny fake mp4 and deletes it again (the data restore can't remove files).
   Tests: 315 API, 61 browser steps.
3zv. (2026-10-15) Volleyball tabs: Games, Videos, Gear. Video games Games page: PlatformSwitch (one platform) replaced by the
   shared PlatformToggles / useCounting (same choice as Dashboard and Stats; ?platform=epic opens on just that one):
   Steam rows from /videogames?show=, Epic / Ubisoft from /videogames/other filtered by OTHER_SHOWS, one table; a
   platform pill per row when 2+ platforms are on; "+ Add a Steam game" / "+ Add a Ubisoft game" by what's shown.
3zw. **Check-over 2** (2026-10-15). pyflakes clean (app + tests: unused timedelta in reading.py, othergames in
   test_videogames.py removed); pip-audit clean; npm audit = the known build-time braces / micromatch / chokidar /
   sass chain inside Excalidraw (no fix exists). ESLint: the 3 deliberate exhaustive-deps warnings only (removed a
   stale disable in readingParts; the combined video games list is now useMemo'd - it was rebuilt + re-sorted on
   every render). Dead code: .other-games / .other-head / .other-hours / .other-pic CSS (old Epic/Ubisoft view)
   deleted; videoType, GAME_FIELDS, weightName, shelfName, StreakPill no longer exported (used in their own file
   only). mention-*, platform-*, s-* classes ARE used (built from data). Security: gameology.photo refuses a redirect
   off cdn.shopify.com; video files: generated names (CHECK), type list + first bytes, nosniff; documented in
   BEFORE_GOING_PUBLIC. Speed: 42 read endpoints all < 50 ms (median 4.8 ms); entry bundle 553 KB / 161 KB gz
   (was 135 KB gz: new hobbies), heavy editors still lazy. Tests: 315 API, 61 browser steps.
3zx. (2026-10-15) Prod data fixes (user's choice, after a backup, also in dev): game 10 (29 Sept "vs BYE 0-0") -> bye
   'no result' via the API; "Somerville House Aquatice Centre" -> "Aquatic" on team 1 (API) and 12 games (SQL).
   backup.ps1 now also copies videos (Copy-Media: robocopy exit codes 0-7 = OK) to backups\media and -CopyTo\media;
   videos deleted in the app stay in the backup. The Settings "Back up now" button is database-only.
3zy. **UI review** (2026-10-15; user asked to take the app "up a notch"). Read-only Playwright tour of 23 pages (desktop
   light + dark, phone) as contact sheets (scratchpad tour.py). Fixed: .home-stats auto-fit (tiles share the row; no
   empty columns - Hobbies cards keep auto-fill); kit Stash value / Spent on kits show "—" when nothing is priced;
   .model-photo.cover for board games + gear (own photos fill the card; product shots keep the white frame); no
   "0 of 0 ticked" bar on an empty wishlist; journal filters (tags + moods left, Day|Month + Sort right; phones: search
   full width, buttons share a row); calendar day dots -> KIND_ICON per kind in its tone (+chess, book tones); chess
   colour marker round (squares looked like checkboxes), accuracy .toFixed(1); chess openings on phones: bar only
   (record and "8 games · 43.8%" overlapped); reading stats: no empty charts; phone nav title one line with ellipsis;
   video games phone toolbar buttons smaller; .empty.card dashed outline. 61 browser steps.
3zz. **Bigger UI changes** (2026-10-15). Home: the flat tile grid became `Glance` (core/Home.jsx GLANCE = Supplies + each
   module with home.Tiles): one card per hobby (uppercase name + icon + chevron link to its first page), the tiles
   inside shown as plain numbers (.glance-tiles hides .stat-icon / border); cards with nothing rendered are hidden
   (:has); a computer: flex-wrap, last row stretches; phones: one horizontal scroll-snap row (78% cards) so Home is
   short. core/EmptyState.jsx (icon, title, text, action) for first-time empties: board games + plays, volleyball
   games / gear / videos, kits, wishlist, journal, books, quotes (filter "no match" messages stay plain). e2e: an empty
   page has two add buttons (toolbar + empty state) -> `.first` for + Add gear / + Add video / + Add a book.
3zza. **Half-star book ratings** (2026-10-15). 43_half_star_ratings.sql: books.rating NUMERIC(2,1), CHECK 0.5-5 in halves (old
   CHECK found by definition and dropped). API rating float multiple_of 0.5; stats.ratings = 10 rows (0.5..5); activity
   "★★★½" (floor + '½' - no `%` in SQL that has parameters: psycopg reads it as a placeholder). Stars: shown = grey row
   with the gold row on top cut to rating/5 width; input = left 40% of a star gives a half (middle/right whole; keyboard
   Enter whole, arrows step halves), "3½" beside it. Ratings chart shows half columns only once a half rating exists.
   Goodreads exports whole stars only. Tests: 315 API, 61 browser steps (clicks a half, then a whole).
3zzb. **Reading: For you (book suggestions)** (2026-10-15). No AI, no account: Open Library search (openlibrary.by_author /
   popular_in, REC_FIELDS adds ratings_average / ratings_count; `_get` lets params override fields). reading_recs.py: seeds()
   = top 5 authors of finished books rated 4★+ (by total stars; seed = their best-rated, the first finished on a tie) and
   genres (finished books by rating, first genre full / others half, want / reading half again; a genre needs 40% of the
   top one's weight; max 3). refresh() (background, REFRESH state, 1 s apart; on an error the old ones stay): per author
   their solo books, rated ones first by year (= series order; unrated / unreleased after), same title -> most rated,
   max 6; per genre (subject search, no juvenile / YA / children's / manga unless that's the genre) one book per author
   (their most-rated, usually a series' book 1), >= 20 ratings, authors you have or already shown skipped, max 8. Both
   skip: no cover, JUNK titles (summaries, box sets, collections...), < 120 pages, other scripts (translations), books
   on your shelves (work id or title key without "(Series, #1)"), dismissed. 44_book_recs.sql: book_recs (stored picks)
   + book_rec_dismissed; settings reading_recs_seeds = the seeds they were made from -> `stale` when seeds change or
   7 days pass; the page starts a refresh once per visit and polls. Routes GET /reading/recommendations, POST .../refresh,
   POST .../{OLnnnW}/want (adds as Want to read), .../dismiss, DELETE .../dismissed (bring back + due). Web RecsView.jsx:
   page /reading/foryou ("More by X - You gave Y 5★", "Popular in Fantasy"), cards with + Want to read / Not interested,
   swipe rows on phones; RecsCard "You might like" (5 covers, round-robin) on the dashboard. SparkleIcon.
   First live run on prod's data: Brown -> Dark Age / Iron Gold / Light Bringer, Dinniman -> DCC #3-#8 in order,
   Islington -> The Strength of the Few; Fantasy -> Mort, LOTR, A Game of Thrones...; SF -> Hitchhiker's, Ender's Game...
   (Open Library's years can be off: Dark Age shows 2015.) Tests: 321 API, 61 browser steps.
   e2e: the kit steps now set the state they need first (set_model via PATCH: Sherman In stash, RX-78-2 In stash with no
   stage, Zero In progress) and read the stash value from the API - they had assumed old data and failed on a fresh
   copy of prod (the user's kits moved on: Zero On hold, RX-78-2 Finished).
3zzc. **Book series + On my shelf** (2026-10-15). 45_book_series_shelf.sql: books.status adds 'owned' ("On my shelf" = yours,
   not started; Want to read = you'd like it); books.series / series_number NUMERIC(6,2); Goodreads-style titles
   "Golden Son (Red Rising Saga, #2)" were split (title "Golden Son") - reading.split_series / _with_series do the same on
   add and Goodreads import (shelf names like owned / on-my-shelf / physical -> owned); book_series_cache (key
   "series|author", source, books JSONB, a week). bookseries.py GET /reading/books/{id}/series: Wikidata first (SPARQL:
   EntitySearch for the series, works P179 of it that aren't series themselves, ordinal P1545, date P577, author P50 must
   match; the series named like ours with the most books wins), covers / work ids from openlibrary.by_author matched by
   title; else Open Library series_books (q series:"X" author:"Y"). Merged with your books (work id / title key); yours
   found in the list learn their series + number. Order: numbered by number, then by year. Live: Red Rising #1-#7 (Red
   God "Not out yet"), DCC #1-#8, Hierarchy, Gentleman Bastard, First Law (+ standalones unnumbered); Farseer / Green
   Bone not found anywhere. Web: SHELVES + 'owned' (purple), seriesText, series line on cards and under the author,
   BookPanel SeriesList ("In this series": #, cover, year / Coming, your shelf or stars -> opens it, "+ Want to read"),
   Edit details Series + Number. Up next = On my shelf first, then Want to read. conftest refuses bookseries._wikidata.
   Tests: 327 API, 61 browser steps (shelf button; a typed series shows and "Couldn't find the other books").
3zzd. **Warhammer kits from Good Games (official UCP)** (2026-10-15). User wanted an API for Warhammer kits, tested on
   Combat Patrol: Adeptus Mechanicus, and the whole AdMech range ("all 33 items") to keep buying from. warhammer.com: AWS
   WAF CAPTCHA (`x-amzn-waf-action: captcha`) for any app -> not used, never bypass. Gameology lacked many kits.
   **Good Games** (goodgames.com.au, Shopify) has the range with the GW code in titles "(59-05)", army tag
   "Faction_Adeptus Mechanicus", barcode = variant SKU, box contents ("1x ..., 10x ..."). User chose its OFFICIAL route
   (robots.txt / agents.md: "AJAX surfaces: agents should use UCP/MCP"): JSON-RPC POST /api/ucp/mcp tools/call
   search_catalog {query, filters.available, pagination limit/cursor} / get_product {id gid}. Every call needs
   meta.ucp-agent.profile = a public JSON (content type application/json, no redirects) with ucp.version, services,
   capabilities, payment_handlers: `ucp-agent.json` (repo root) asks only dev.ucp.shopping.catalog.search / .lookup +
   dev.shopify.catalog (without them: "Tool not found: search_catalog"). Served by jsDelivr from git TAG ucp-agent-1
   (raw.githubusercontent is text/plain -> "Invalid content type"; a jsDelivr BRANCH URL stays cached for hours after a
   change). New profile version = new tag + goodgames.PROFILE; UCP_PROFILE env overrides. Gotchas: filters.available
   true = in stock ONLY, false = sold out ONLY -> search both; get_product / lookup_catalog have NO tags -> get() finds the
   same product by SKU in a search for its tags; titles have U+FFFD for dashes (-> –); minis = sum of "Nx Name" with
   brackets removed ("(which can alternatively be built as 3x ...)" double-counted: 37 -> 19). goodgames.py kit():
   id, title, name ("Adeptus Mechanicus - Onager Dunecrawler" -> "Onager Dunecrawler"; "Combat Patrol: Adeptus
   Mechanicus"), code, army, figures, contents, barcode (13 digits), price, available, url, image (cdn.shopify only),
   is_kit (NOT_KITS: codex, datacards, index, dice, collectibles, books...). army_range = tagged with the army, or the army
   in the title + a GW code (Thulia Ghuld isn't tagged), by code. warhammer.py: GET /warhammer/search, /warhammer/army
   (kept an hour in memory, ?refresh), /warhammer/armies (yours + quick picks), /lookup/warhammer/{code} (GW code /
   barcode / name -> choices with every word / id:<n>; product_info brand Games Workshop, product_code = GW code, series =
   army, description "GW 59-05 · Adeptus Mechanicus · 19 minis · Good Games $192.77", photo, barcode -> scan "known"),
   POST /warhammer/want {id} (Wanted Warhammer model; 409 if you have it). Every kit has my_model. Web: Models tab
   "Warhammer" (WarhammerRange.jsx: army chip-filters, "Another army", All / In stock / Don't have, cards with GW code +
   stock badges, "+ Wanted" / "Yours · Wanted", "Good Games ↗"), ModelForm maker Games Workshop (+ Scan the box; fills
   name, Army, Minis, code), ModelPanel SOURCES 'Games Workshop'. ShieldIcon. Live: AdMech 28 kits, 10 in stock.
   Tests: 332 API (test_warhammer.py fakes _call; conftest refuses goodgames._call), 62 browser steps (warhammer_range,
   live; skips if the shop can't be reached).
3zze. **Gundam tab, board game types, To sell** (2026-10-16).
   - Models tab "Gundam" (GundamRange.jsx; KitCard shared with WarhammerRange, takes badge + meta): Good Games via the same
     UCP client. goodgames.base() (shared fields) / kit() (Warhammer) / gunpla(): grade (hlj.grade_of), scale (Scale_ tag, else
     "1/144" or "1-144" in the title), code = hlj.product_code_for(barcode) -> G50xxxxx (so the user's HLJ-looked-up kits match
     "Yours"), is_kit (NOT_GUNPLA: card game, decks, Gundam Universe / Robot Spirits figures, markers, tools...; Bandai barcode
     prefixes 4573102 / 4549660 / 4543112 or tag Model). gunpla_name tidies the shop's titles ("Gundam HG MSN-06S SINANJU
     Mobile Suit" -> "MSN-06S Sinanju"). gunpla_search: no words = "gundam" in stock only (4 pages); words = both. gundam.py:
     GET /gundam/kits?q= (kept an hour), POST /gundam/want {id} (Wanted Gundam model, grade, scale, photo). Live: 160 in stock.
     warhammer.store() / shop_price() shared. NOT_KITS also drops Citadel paints / sprays / primers / brushes.
   - Good Games rate-limits bursts (429 seen after a day of testing, gone a minute later, no Retry-After): PAUSE 1 s, one
     retry after Retry-After (<= 30 s) or RETRY_WAIT 3 s, then the friendly message. Web: an older answer is ignored when a
     newer army / search was asked (`latest` ref) - the e2e caught Ultramarines overwriting Adeptus Mechanicus.
   - Board games: 46_board_game_kind.sql kind game | expansion | other, base_game_id (self FK, SET NULL, not itself),
     shop_expansions TEXT[]; backfill guesses from names. Gameology tag "Board Game BEA: Base Game | Expansion | Board Game
     Accessorie" -> gameology.kind_of(); a base product lists "Expansion: <handle>" -> link_add_ons() (else name prefix).
     Kind set on add from the shop (or replace / set_kind); POST /board-games/check-types (background, 1 s apart, KINDS_CHECK)
     re-reads every shop game - placed BEFORE /board-games/{game_id} (else "check-types" is parsed as an int -> 422).
     Rows: kind, base_game_id, base_name, add_ons. Web: GamesView type chips + status chips, <details> groups Base games /
     Expansions / Other, "Expansion for Scythe" / "+ 4 expansions / extras"; GameForm Type + "Expansion for" select; panel line
     links to the base. Live on prod's data: 3 Scythe expansions + Metal Coins (other) under Scythe, 14 base games.
   - 47_board_game_to_sell.sql: status "To sell" (still counts as owned; summary.to_sell; tone low).
   - dev.ps1 -Refresh now empties dev's public schema and restores without --clean (a dev-only FK made --clean fail).
   - User asked about board games from Good Games instead of Gameology: its tags lack min players, play time, numeric weight
     and the BEA type tag (only max players, age, Complexity_ word, Mechanic_ / Theme_) - suggested keeping Gameology, maybe
     adding Good Games price / stock. Awaiting the user's answer.
   - Tests: 339 API, 64 browser steps (gundam_range live, board_game_kinds).
3zzf. **Board games: Gameology first, Good Games fills the holes** (2026-10-16, user's choice). GET /board-games/lookup now returns
   {results, asked_good_games, notes}: Gameology results (source gameology) first; Good Games (goodgames.board_games, same UCP
   client) is asked only when no Gameology title has every typed word, or with more=true ("Not here? Search Good Games too") -
   the box searches as you type and Good Games rate-limits; answers kept 10 min (_gg_found). Good Games results: titles with
   every word only (its search is loose), same name as a Gameology result dropped, tags -> max_players (Maximum Players_),
   min_age (Recommended Age_), complexity word (Complexity_), categories (Theme_), mechanisms (Mechanic_); kind expansion only
   from the name; no min players / play time / weight / publisher. One shop down: the other's results + notes; both: 502.
   POST /board-games {gg_id} and POST /board-games/{id}/shop {gg_id} fill in from Good Games (shop_game reads it server-side).
   48_board_game_shop_name.sql board_games.shop_name Gameology | Good Games (old shop rows = Gameology); the panel link says
   which; check-types only re-reads Gameology games. Web: ShopFind "Find it at a shop", Good Games pill, complexity in the
   meta, shopRef(r) in api.js, gameMeta "up to N players". Live: "scythe" + Good Games -> Scythe Encounters, Rise of Fenris,
   Scythe & Expeditions Metal Coins. Prod data fix: SUP-0006 renamed "Craft Bond 20g" (was "Craft Bind"). Tests: 343 API.
3zzg. **Faster promotes** (2026-10-16). Measured: API tests ~46 s (pytest ~35 s + ~10 s running 48 db\init files one psql each),
   walk-through ~2 min 15 s (+7 s pip install per run), prod rebuild ~30 s (web vite build ~23 s, api ~2 s), push ~5 s - and
   promote re-ran both suites on code already tested minutes before. Now:
   - "passed" stamps: scripts\common.ps1 Get-CodeHash = git write-tree of a scratch copy of the index after `git add -A` (the
     tree the code on disk would commit as; equals dev^{tree} once committed unchanged); Set-Stamp / Get-Stamp in
     <copy>\.tested\{api,e2e,built}.txt (git-ignored; line 1 hash, line 2 time). run_tests.ps1 stamps api on a full pass (not
     -k); dev.ps1 Start-Dev stamps built after a healthy build; run_e2e.ps1 stamps e2e only if built == code on disk (else a
     note: the running app is older than the code). promote.ps1 skips step 3 when dev is clean and api (+ e2e unless -Quick)
     == dev^{tree}; -Retest forces; otherwise it runs test_all.ps1.
   - test_all.ps1: run_tests.ps1 and run_e2e.ps1 side by side (Start-Process, logs in .tested\*.log; `$null = $p.Handle` right
     after starting or PS 5.1's ExitCode reads empty). 144 s for both vs 148 s for the walk-through alone. -Quick = API only.
   - run_tests.ps1: all db\init files in ONE psql session (\echo "applying <file>" before each names a failure).
   - run_e2e.ps1: image offtheclock-e2e:1.47.0 from e2e\Dockerfile (Playwright + its pip package, built once, cached;
     e2e\.dockerignore keeps the context empty).
   Use .	est_all.ps1 in dev after changes; the next promote then only backs up, rebuilds, restarts and pushes (~1 minute).
   The fingerprint leaves out top-level *.md (Get-TreeHash filters `git ls-tree` and hashes the rest), so editing notes after
   testing doesn't force a re-test; any code / script / migration change does. Side by side measured 108-144 s.
3zzg. **Video games: platform tap = "just this one", Find a game** (2026-10-16). PlatformToggles: with every platform on, a
   tap keeps only that one; then taps add / remove (one stays on); an "All" button shows when not all are on. Find a game
   (api/app/vgfind.py, router before videogames): GET /videogames/find?q= (steam.store_search - split out of find_app -
   type app only, soundtracks / OST / artbooks dropped by NOT_GAMES with \b word edges; `yours` = Steam game or the Epic /
   Ubisoft game whose Steam version it is), GET /videogames/scout/{app_id} (store_items + schema + global %, SteamHunters
   game + unobtainable; SteamHunters down -> a note; achievements most-held first, colour icons; ultra_rare <= 5%,
   rarest_percent, perfect_rate). Both kept an hour in memory, nothing stored. Web FindGamePanel.jsx (panel 'findgame';
   "Find a game" in the Games toolbar and "find it by name" in + Add a game): search as you type, pick -> picture, counts,
   the panel's Compared (exported, `hint` prop) and AchievementList (.scout-list un-dims rows); "Open yours" or "I've played
   it - track it" (= + Add a game by app id). conftest refuses steam.store_search. Tests: 344 API, 64 browser steps
   (find step is live; skips if Steam can't be reached).
3zzh. **Warhammer: each mini its own step; Epic / Ubisoft games by hand** (2026-10-16).
   - 49_model_minis.sql: model_minis (model_id CASCADE, unit, name, stage NULL = not started, sort_order);
     product_info.kit_units JSONB = goodgames.units_of(description) ("1x A, 10x B ... and 3 C"; brackets / "which can
     alternatively be built as" skipped; name stops at filler words "All models come..."; kit figures = sum of units, else
     _figures). api/app/minis.py: POST /models/{id}/minis {unit, count}, POST .../minis/from-box (kit_units, else asks Good
     Games by GW code via warhammer._pick + _store; 404 = add by hand), PATCH /model-minis/{id} {stage, name, unit}, PUT
     .../minis/stage {mini_ids, stage}, PUT .../minis/unit {unit, to}, DELETE /model-minis/{id}, DELETE .../minis?unit=.
     sync(): the box follows its minis - stage = the step EVERY mini reached (skipped_steps []), figures = count,
     figures_done = Complete ones, In progress once any mini has a step, Finished when all Complete (tidy_model rules).
     models.update_model -> minis.after_model_change: a box step brings minis behind it up; un-finishing takes Complete
     minis back to the box's step. fetch_model returns `minis`; MODEL_SELECT `box_units`. Web MinisTracker.jsx (Warhammer,
     not Wanted): setup (from the box / by hand), then units as folds ("All primed"), "Set all to..." per unit and whole box,
     a pill per step per mini (tap last done = back a step), # / name, rename / remove unit, + Add minis. BuildSteps is
     hidden once minis exist.
   - Games toolbar = Sync now + Find a game (the + Add forms and AddUbisoftGame are gone). FindGamePanel: Steam / Ubisoft /
     Epic Games switch; Ubisoft / Epic search Exophase (exophase.search(words, "uplay"|"epic"): master id, name, picture
     from m.exophase.com, page) via GET /videogames/other/find (cached an hour; `_seen` keeps what was shown; declared
     before /videogames/other/{game_id}); pick or "+ Add '<words>' by hand" -> AddOtherGame (hours; Ubisoft also numbers)
     -> POST /videogames/other {platform, name, exo_id?, hours, done, total} (409 if the same name is on that platform;
     exo_id must have been shown by a search). Hand-added games have no source_id (removable); sync skips their Epic
     earned list. Panel says "Hours only - no achievements tracked" (Fortnite, 569 h). Gotcha: in a panel that opens
     another, call onClose() BEFORE openPanel() - the other way round closes the new panel too.
   - Tests: 348 API, 65 browser steps (warhammer_minis; video_games adds + removes an Epic game by hand).
3zzi. **Photos pasted or from a web address** (2026-10-16; user: gear has no lookups, wants to copy a picture from the web /
   paste from the clipboard). PhotoPick (every image picker: gear, board games, kits, build log, product photos) gets
   "Paste or link" ("Link" on touch screens): a pop-over box (.photo-pick-wrap / .paste-box, absolute - the buttons often
   sit in a narrow column) that takes Ctrl+V of a picture (clipboardData file), a dropped picture or link, a data:image
   address (decoded in the browser; CSP connect-src would block fetch), or a web address -> POST /api/photo-from-url
   (api/app/webphoto.py) which returns the picture's bytes; the browser then shrinks + saves it as usual. SSRF guard:
   http(s) on 80/443 only, every resolved address must be ipaddress.is_global (no localhost / Docker / LAN), redirects
   followed by hand (<= 4) and each re-checked, streamed with a 5 MB cap, type from the first bytes (JPEG/PNG/WebP/GIF;
   not SVG). Tests: test_webphoto.py (fake DNS + MockTransport); e2e pastes a 1x1 PNG onto new gear.
3zzj. **Wanted gear** (2026-10-16). 50_gear_wanted.sql: gear condition 'Wanted' (old CHECK found by definition, replaced by
   gear_condition_check); db.GEAR_CONDITIONS starts with Wanted. /gear order: in use, then Wanted, then Retired; summary
   gear_wanted. PATCH from Wanted to an owned condition with no purchase date dates it today (DB current_date).
   Web: "+ Want" (GearPanel wanted=true preselects Wanted, "Add to wanted"), a "Wanted" group below your gear, "N wanted"
   in the summary, purple badge / picker button. Wanted = not bought yet: the form hides Bought on + Price paid
   (FormPanel `hide`, values still sent) and the API clears both for Wanted (not_bought_yet). Tests: 362 API, 65 browser steps.
3zzk. **Volleyball clips + highlight videos; car placeholder** (2026-10-16).
   - 51_volleyball_clips.sql: volleyball_clips (video_id CASCADE, title, start_s / end_s NUMERIC(9,2), end > start);
     volleyball_videos.processing (NULL | 'making' | 'failed: why') + made_from. api/app/vbclips.py: clips = bookmarks
     (GET/POST /volleyball/videos/{id}/clips, PATCH/DELETE /volleyball/clips/{id}; times are floats from the player,
     rounded to hundredths - the first version used Decimal(decimal_places=2) and refused 12.3456789; <= 30 min; 409 for
     links / unfinished videos). POST /volleyball/highlights {title, clip_ids} (202) -> new video (topic Highlights, game
     if all from one) 'making'; BackgroundTasks render(): ffprobe (rotation from side_data: Samsung portrait = -90),
     ffmpeg -ss/-t per input, scale+pad to the first clip's shape (long side <= 1920, even), fps 30, stereo 48k (anullsrc
     for silent clips), concat filter, libx264 veryfast crf 23 + aac, +faststart, -progress pipe -> PROGRESS[id]; one at a
     time (lock), nice 10; .part then rename. GET /volleyball/highlights/{id} = progress. main lifespan:
     forget_unfinished() marks 'making' as failed + removes *.part. GET .../file?download=true = attachment named after
     the title. ffmpeg 7.1 from Debian in api/Dockerfile (image ~1 GB). Real footage: prod's full game is HEVC 1080p
     portrait, 37.5 min / 4.15 GB; a 20 s cut took 4.9 s -> 1080x1920 H.264, 5 MB.
     Web ClipEditor.jsx (in VideoPanel, wide drawer): Mark start / Mark end (times tap to jump), name, Preview, Save clip;
     clip list (tick, play - stops at the end, delete), Play all / Play N ticked, Make a highlight video -> title ->
     toast; Making (polls 2 s, progress bar / failed message); Download link. VideosView: Making... / Couldn't be made
     cards, polls 3 s while any is making, "N clips". GOTCHA: Playwright's Chromium can't play H.264 MP4 (no licence) -
     browser tests of real playback need WebM; the walkthrough adds clips through the API.
   - modules/car: "Building my car" (Modified Toyota 86) placeholder - one page with an EmptyState; manifest
     underConstruction: true -> Navigation's UnderConstruction (amber WrenchIcon) after the name in the sidebar and on the
     Hobbies page. CarIcon, WrenchIcon. Tests: 367 API (test_vbclips.py runs the real ffmpeg on generated videos), 65 steps.
3zzl. **Raw or edited videos** (2026-10-16). 52_video_edit.sql volleyball_videos.edit raw | edited (NULL = a link); backfill:
   made_from -> edited, files -> raw. add_video defaults an upload to raw; highlights are edited; VideoIn / VideoPatch
   `edit`. Web: "Raw or edited" select in the video form, Raw / Edited pill on cards (.edit-pill), All | Raw | Edited
   segmented filter on Videos (only when both exist). Spanner colour: .side-link svg (tint) needed an override.
   Tests: 368 API, 65 browser steps.
3zzm. **Calendar: All day switch; events for every hobby** (2026-10-16). EventPanel: an "All day" switch (role=switch) after
   the Day field (two RecordFields groups around it) hides From / Until and sends them null (no start_time = all day,
   as before); an existing event without a time opens with it on. Month cells: .day-event.all-day = solid tone bar
   (text in --surface; phones keep their 4px bars). 53_calendar_hobbies.sql + db.MODULE_IDS: events can be any module
   (the old CHECK only allowed models / boardgames / volleyball, so picking Chess etc. failed). HOBBY_TONE for all.
   Tests: 369 API, 65 browser steps.
3zzn. **Board games elsewhere + abandoned; volleyball Coach; chess layout** (2026-10-16).
   - 54_board_game_elsewhere.sql: board game status 'Played elsewhere' (a friend's copy: not counted as owned) and
     board_game_plays.finished (false = abandoned; the API drops the winner). POST /board-games/plays {game_name, ...play}
     finds the game by name (any case) or adds it as Played elsewhere. PLAY_SELECT game_status; summary abandoned +
     played_elsewhere. PlayForm: "Someone else's game (not in my list)..." option + "Their game" box, Played elsewhere
     optgroup, "Didn't finish (abandoned)" switch (hides Who won); plays show "played elsewhere" / an Abandoned pill.
   - 55_volleyball_coach.sql + api/app/vbcoach.py: notes kind drill | fix | position (fix status working on | sorted,
     CHECK), skill / position (suggested lists), body, links TEXT[] (http(s) only), video_ids INT[] (your uploads; NOTE_SELECT
     joins their titles), pinned, starter. POST /volleyball/coach/starter adds 7 drills + 6 positions written for the app
     (no video links - each note has a "Find videos on YouTube" search link instead), once (409). Web Coach.jsx: Coach tab
     (Games, Videos, Coach, Gear) - cards, Show chips (All / Working on / Drills / Positions / Sorted), skill chips,
     CoachNotePanel (kind + status segmented, links with YouTube pictures, your videos picker, pin). WhistleIcon.
   - Chess dashboard: rating chart + Over the board stacked in the left column (.home-stack) - it used to start a new
     grid row below the tall Recent games card.
   - Tests: 372 API, 67 browser steps (board_game_elsewhere, volleyball_coach).
3zzo. **Travel placeholder; mainstream book picks** (2026-10-16). modules/travel (like car: underConstruction, SuitcaseIcon,
   one empty page); 56_calendar_travel.sql + MODULE_IDS. Reading "Popular now in <genre>": openlibrary.popular_in sorts
   by want_to_read (most added to readers' Want to Read lists - BookTok / bestsellers: Fourth Wing, Powerless, Midnight
   Library...) with first_publish_year >= 2000 (RECENT); sort=rating gave classics; sort=trending was noisy (manga,
   translations) and trending_yearly answered HTTP 500. Translations in Latin script (Cadáver exquisito) still slip
   through - "Not interested" hides them.
3zzp. **Video games Friends tab** (2026-10-16). Official Steam Web API: steam.friend_ids (GetFriendList; 401 = the user's
   friends list is PRIVATE - it is, as of today -> FriendsPrivate with how to make it public), steam.summaries
   (GetPlayerSummaries, 100 a call: name, avatar, public, status, playing). 57_videogame_friends.sql vg_friends (steam_id,
   from_list / by_hand / hidden, status, compared_at, compare_error, games_owned) + vg_friend_games (their playtime,
   done / total per shared game). api/app/vgfriends.py (router before videogames): GET /videogames/friends, POST .../refresh
   (at most every 10 min unless force; people who leave the list and weren't added by hand are forgotten), POST {profile}
   (steam.resolve; not yourself), DELETE (by hand: removed; from the list: hidden), POST .../{id}/compare (background:
   their owned games - Game details must be public - then player_achievements per game you both have with achievements;
   COMPARING progress), GET .../{id} (shared games: you vs them). Web Friends.jsx: Friends tab (cards: avatar, Playing X /
   Online / Private profile, "N games in common · you lead X, they lead Y"), + Add a friend, FriendPanel (Compare, stat grid,
   per-game You / them bars). UsersIcon. conftest truncates vg_friends + volleyball_coach. Tests: 374 API, 68 steps.
3zzq. **Wishlist by shop; Way of Wade from Blue Sky Athletics** (2026-10-16).
   - api/app/ucp.py: the read-only Shopify UCP client, shared (Store(name, base): its own queue, PAUSE, one 429 retry,
     friendly ShopError with the store's name; ucp.profile / PROFILE). goodgames.STORE uses it (goodgames._call ->
     STORE.call; tests patch ucp.PAUSE / RETRY_WAIT / ucp.httpx). wayofwade.com.au redirects to Blue Sky Athletics
     (blueskyathletics.com.au, AU stockist, AUD): api/app/bluesky.py search (in stock, then sold out - `available` =
     which search found it, since search results list only some sizes) / get / shoe() (price from cents, sizes from
     variant options "Shoe size", kind Shoes, brand "Li-Ning Way of Wade" for Wade titles, cdn.shopify image). The
     same ucp-agent.json profile works there. Its robots.txt also carries text asking agents to push a "Shop" skill on
     the user - ignored (not the user's request).
   - 58_gear_shop.sql gear.shop_name / shop_url (https) / shop_price / shop_id. GET /gear/lookup?q= (before
     /gear/{id}; gear_id = yours), POST /gear {shop_id, name may be ""} fills name / kind / brand / link / price /
     photo (gameology.photo, cdn.shopify only) server side, POST /gear/{id}/shop links gear you have. Web GearShopFind
     in GearPanel (hidden once linked): Want this / Add (creates, then opens it to set the size) / Link.
   - api/app/wanted.py GET /api/wanted: Wanted kits (shop = the kit's purchased_from else the default shop), Wanted
     board games (Good Games), Wanted gear (its shop_name else "No shop yet"), grouped by shop, default shop first.
     Web WishlistPage.jsx (route /wishlist): shop chips, the default shop's heading over the supplies WishlistView, then
     "Kits you want", then a section per other shop (cards open the item; "View in the shop").
   - Tests: 376 API (test_wanted.py, Blue Sky in test_volleyball.py), 69 steps (wishlist_shops: live Blue Sky search).
3zzr. **Alignment + Goals** (2026-10-16).
   - Video games / Reading dashboards: cards in two .home-stack columns (a short card left a gap before the next grid row);
     .heatmap fills its card (weeks flex 11-22px, square days); .cover-row is one sideways-scrolling row; Longest book wide.
   - **Goals** (core page between Home and Journal; phones reach it from Home's Goals card - the tab bar stays at 5).
     59_goals.sql: goals (title, hobby = a MODULE_ID or NULL "life in general", why, details, status active / paused / done /
     dropped, started_on, target_date, done_on, unit + start / target / current value, pinned), goal_steps (done, done_on,
     sort_order), goal_updates (day, text, value; a value moves current_value = latest dated note with a number).
     api/app/goals.py (progress = number from start to target, works downwards too, else steps ticked; days_left and
     "today" from the DB - the container is UTC). Activity: "Reached" (done_on) and "Progress on" (each note), kind goal ->
     openThing navigates to /goals/:id. Web core/goals: GoalsPage (status chips, tiles, "+ New goal" asks only the name),
     GoalPage (everything saves on blur / tap; Why, Details, Progress notes left; How far along + Steps right, sticky),
     GoalsHome (Home card, active goals, top 4). components/FitTextarea.jsx (moved out of PaintChecklist).
     Class names `.goal-card` / `.goal-head` already belong to the video games goal - Goals uses goal-tile / goal-top.
   - Tests: 379 API (test_goals.py), 70 browser steps (goals).
   - Timeframes (user asked for New Year's and 3-year goals): 60_goal_timeframe.sql goals.timeframe year | three_years
     (NULL = no set time) + period_start (the year; 3 years = start..start+2). API: a new one with no year = this year (DB
     date); target_date follows the period's end (31 Dec) unless you'd picked another day. Web: "When" choice on + New goal
     (This year / Next year / 3 years from either / No set time; periodChoices), a When select on the goal page; the list is
     in sections (groupGoals): this year's, 3-year goals running now, next year's and later, Other goals, past years'
     (with "N of M done"); the status filter now starts on All. The user already had goals in dev (Career Change, Complete
     MBA, Get Engaged, Div 2 Volleyball, Triathlon). 380 API tests, 70 browser steps.
3zzs. **Precision shooting placeholder** (2026-10-16): modules/shooting (like car / travel: underConstruction, CrosshairIcon, one
   empty Sessions page); 61_calendar_shooting.sql + MODULE_IDS; calendar tone 'out'. e2e: 9 hobby cards.
4. ~~Excel reads via Power Query~~ - dropped
5. ~~Excel writes via VBA buttons~~ - dropped
6. MCP server whose tools call the API (port 8000), so Claude can answer "what am I low on?"
   and update stock

DBeaver connection confirmed working (2026-10-11).


## State in the first week (2026-10-11 to 10-13)
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

## Since then

3zzt. **Health check: fixes** (2026-10-16; user asked for a critical review, then "fix everything"). Rated B+ (78/100).
   - Walk-through isolation: run_e2e.ps1 now starts a THROWAWAY copy (compose project hobby-e2e, volume hobby_e2e_pgdata,
     ports 5436/8003/8083) from the images the copy runs + a pg_dump of its data; videos are hard links in .e2e\media
     (deleting one in the test leaves yours); its backups folder holds that dump (Settings > Backups lists it);
     DAILY_SYNCS=off. Assert-E2EConfig refuses to run `down -v` unless compose resolved to hobby-e2e + its own volume.
     Dev's data is never touched, so the "tell the user before e2e" rule is gone. docker-compose: BACKUP_PATH /
     MEDIA_PATH / DAILY_SYNCS (defaults = before). walkthrough.py logs every HTTP >= 400 with its address.
   - Weekly site check (api/app/sitecheck.py, 62_site_checks.sql): one real look-up per site the app reads (Tamiya
     81701, Hasegawa JT86, HLJ RX-78-2 barcode, Good Games AdMech Combat Patrol, Gameology Catan, Blue Sky Way of Wade,
     Open Library Way of Kings, Steam store Portal 2, SteamHunters 620, Exophase Portal 2), checking the answer's shape;
     failing_since kept. Settings > Lookup sites (Check now), Home warns when one fails. All 10 OK on first run.
   - Quality gates in `npm run build`: web/scripts/check-css-clashes.js (a class's plain rule defined in two sections
     of styles.css fails the build) then ESLint 9.30.1 (web/eslint.config.js, --max-warnings 0; the 3 deliberate
     exhaustive-deps cases carry eslint-disable comments saying why). The check found a REAL bug from Goals: its
     .goal-bar / .goal-percent restyled the video games and reading goal bars (now .goal-meter / .goal-big-percent).
     9 duplicated plain rules merged (pixel-compared 78 screenshots before / after: no change).
   - Splits: gear routes -> api/app/gear.py; Steam sync -> api/app/vgsync.py (videogames.py keeps routes + maths);
     Goodreads import + covers -> api/app/readimport.py (COVERS state stays in reading.py); web GearPanel.jsx out of
     VolleyballPanels.jsx (FormPanel exported).
   - npm: override sass 1.83.4 (chokidar 4, no braces) -> npm audit 0. Docker build cache pruned (8.3 GB).
   - api/Dockerfile: uvicorn --workers 1 on purpose (in-memory progress + daily loops). Daily Steam loop logs failures.
   - Firewall: both web rules now allow LocalSubnet + Tailscale 100.64.0.0/10 (Tailscale's profile is Private).
   - Backups to the network drive: the Seagate on the Telstra modem's USB share, \\10.0.0.138\Seagate_ExpansionDesk_2_917f
     (guest, ~2 MB/s; big fast writes hung it once - unplug/replug fixed it). backup.ps1 -CopyTo keeps $Keep there,
     checks the copy's hash, and copies videos with robocopy /Z /R:3 /W:30 /IPG:5 for \\ paths. The nightly task
     passes -CopyTo "...\Off the Clock backups". Prod's 5 GB of videos seeded by hand once.
3zzu. **Hiking placeholder** (2026-10-16): modules/hiking (like shooting: underConstruction, BootIcon, one empty Hikes page);
   63_calendar_hiking.sql + MODULE_IDS; calendar tone 'ok'. e2e: 10 hobby cards.
3zzv. **Hiking: AllTrails import** (2026-10-16; user: "build an exporter for AllTrails with as much information as possible").
   AllTrails has no public API (partners only) and its site is bot-protected, so the way in is the user's own GPX
   export, uploaded (like the Goodreads CSV). 64_hikes.sql; api/app/gpx.py (pure: parse + measure) and hiking.py.
   - From the track: distance (per segment - a pause's gap isn't walked), moving time (faster than 0.3 m/s between
     points) and total time, climb / descent (elevation smoothed over 5 points with the window narrowing at the ends so
     the start and summit keep their height, then a 3 m hysteresis - raw GPS elevation wobbles and doubles the climb),
     highest / lowest point, per-km splits (moving time, up, down), loop or one way (start and end within 250 m),
     waypoints, the AllTrails link from <link>, the description -> notes. The track is thinned to 1500 points evenly by
     distance for drawing; the original file is kept (download it back). sha256 = the same file twice is skipped.
   - Safety: files with <!DOCTYPE / <!ENTITY are refused before parsing (XML bombs); 30 MB cap.
   - The day hiked = the start time in the database's time zone (GPX times are UTC).
   - Web (modules/hiking): Dashboard (this year, km per month, personal bests, latest), Hikes (search, year), the hike
     panel (numbers, route drawn as SVG - longitude scaled by cos(latitude), north up, a scale bar - and the elevation
     profile: hovering one marks the point on the other; splits; waypoints; details form; notes; photo; links to AllTrails,
     the GPX, OpenStreetMap). No map tiles (an outside source with its own terms). Log a hike by hand too.
   - Activity "Hiked" (kind hike), so Home and the calendar show hikes. Home tile: km this year (only once there's a hike).
   - RecordFields: a number field can take a step (0.1 for km).
3zzw. **Hiking: maps, your photos, landmarks** (2026-10-16; user picked all four: topo map, satellite, own photos on the
   track, landmarks). 64_hikes.sql was reworked before it reached prod (dev's hikes table dropped and made again):
   the single cover photo became hike_photos; hikes gained landmarks / nearby_photos / landmarks_at / landmarks_error.
   - Map: Leaflet 1.9.4 (plain Leaflet in an effect, no react-leaflet), OpenTopoMap or Esri World Imagery (toggle,
     remembered in localStorage), route with a white edge, start / finish, waypoints, landmark diamonds with a popup
     (built as DOM elements - OSM names are never HTML), your photos as thumbnail pins; the profile's hover point shows
     on the map. Scroll-wheel zoom off (the panel scrolls). Tiles get Referrer-Policy strict-origin-when-cross-origin
     (the app's own policy is same-origin, which sends none; tile servers ask for one).
   - Your photos: EXIF read in the browser BEFORE shrinking (canvas re-encoding drops it): GPS + DateTimeOriginal
     (+ OffsetTimeOriginal). The API places each: by GPS (on the track if within 1 km) or by time (interpolated between
     track points; a camera time without a zone is read in the database's zone). Gallery, a viewer (caption, prev /
     next, Escape closes only it - stopPropagation before the drawer's document listener), marks on the profile.
     1600 px max. A hike's thumbnail = its first photo along the way.
   - Landmarks: Overpass, one query (6 kinds, `around:250` a 60-point line along the track) in the background after an
     import, then Wikidata P18 / wikimedia_commons -> Commons thumbnails with author + licence. Nearby photos: Commons
     geosearch around up to 4 points, kept within 200 m of the track, 12 spread along it. Overpass was slow (38 s
     queue) and both mirrors returned 500 on the day, so: main server only, retries after 20 s / 60 s, results saved.
     "Look again" re-runs; an error is shown and the last results kept. DAILY_SYNCS=off (the walk-through copy)
     skips it; the walk-through also serves the map tiles a blank PNG. Both sources are on the weekly site check.
3zzx. **Hiking gear** (2026-10-17; "equipment like volleyball for hiking"). gear.hobby existed from the start for this;
   65_hiking_gear.sql allows 'hiking' and adds hike_gear (which gear went on which hike). GET /gear?hobby=; GEAR_SELECT
   adds hikes + hiked_m; volleyball's summary counts only its own gear. PUT /hiking/hikes/{id}/gear (hiking gear only);
   a hike carries its gear and last_gear_ids ("Same as last hike": the previous hike that had gear, minus retired /
   wanted). Web: GearView / GearPanel take a hobby (kinds list per hobby; the Blue Sky shop search stays volleyball's -
   it's a court-sports shop); Hiking -> Gear tab; "Gear used" on each hike; cards show "N hikes · X km".
3zzy. **Gardening placeholder** (2026-10-18): modules/gardening (like shooting: underConstruction, SproutIcon, one empty
   Garden page); 66_calendar_gardening.sql + MODULE_IDS; calendar tone 'ok'. e2e: 11 hobby cards.   The run crossed midnight and found two morning-only problems: the phone calendar's activity icons (4 + "+N")
   didn't wrap, so a busy day widened the page by 3 px (.day-dots now wraps); and the goals step looked for its goal
   in Home's top 8, which date-only items (filed at midday) fill in the morning - it checks the feed instead.
3zzz. **Gardening, fully built** (2026-10-18; "everything you could add to a gardening app", Bunnings, a visual layout
   with what's in each space and timings, notes and photos per item; the user lives in an apartment).
   - Bunnings: no public API, no official catalogue (not Shopify - no UCP). robots.txt disallows /search and /api/ but
     ALLOWS product pages (/*_p*), so bunnings.py reads only a product page the user pasted / shared, 2 s apart, honest
     User-Agent. The page is Next.js: everything is in __NEXT_DATA__ props.pageProps.dehydratedState.queries
     ("retail-product": name, itemNumber, manufacturer, averageRating, numberOfReviews, weight, allCategories, feature,
     installationInformation, images; "product-retail-price": value for the default store). Cloudflare's passive
     "challenge-platform" script is on the page but it's not a wall - a real challenge (no __NEXT_DATA__) is an error.
     Photos only from media.bunnings.com.au at &t=w1200 (the size their page uses; w600 is a 404). "Search Bunnings" opens their search in the user's browser.
     Tests use a made-up page (their page isn't copied into the repo).
   - Open-Meteo for weather tips (heat >= 30/35, gusts >= 45/60 for outdoor spaces, rain >= 5 mm for uncovered ones,
     nights <= 5, UV >= 11); forecast cached an hour; place search sets garden_settings (lat / lon in the DB only).
   - 67_garden.sql: garden_settings (climate zone), spaces (size, open side + facing, sun h, covered, wind, grow light,
     weight limit), containers (placed in cm, kind, shape, litres, level, self-watering, photo), guides, plantings (stage,
     dates, rhythm, last watered / fed, harvest window, parent = propagated from, item = seed packet), logs (kinds incl.
     Harvested amount + unit, problem tags), photos (on logs), tasks (repeat_days moves due_on on), items (supplies, seed
     bank, Bunnings fields). 68_garden_guides.sql: 51 plants written for pots in an apartment, sowing months for 5 zones.
   - Due dates in SQL (PLANTING_SELECT): water = last + every (x2 in a self-watering pot), never watered = today; feed =
     (last fed or started) + every; harvest window from the guide's days minus a head start by source (seedling 21 d).
     Warnings: too little light (sun + grow light hours vs the guide), pot too small, out of sowing season.
   - Layout (LayoutView.jsx): the space to scale (min of width / 520 px tall), 50 cm grid, the open side as an amber bar
     with facing + sun, a compass arrow (side angle - bearing), containers dragged with pointer capture (snap 5 cm, kept
     inside), corner to resize, arrow keys too; a tap (no move) opens it. Badges: water due, ready, warnings.
   - Activity: Sowed / Planted, Harvested, Repotted, Spotted (pest / problem), Treated, Sprouted, Flowered, Photographed,
     Noted (not each watering). Wanted supplies go on the Wishlist under Bunnings. Site check: 14 sites.
   - Section tabs now scroll sideways when they don't fit (six Gardening tabs on a phone); max-width 640 px.
   - e2e: rules-of-hooks false positive from a `while` loop in a component - moved into a helper. A label wrapped round a
     <select> includes every option's text in its name (get_by_label matched the plant list).   - Regional plants (user, 2026-10-18: "a lot of the flowers and veg don't work", e.g. a 100mm leek in stock at Stafford):
     live plants are sold by region, and with no store chosen their pages are a 404 for Bunnings' default store (Mentone,
     VIC). The browser's chosen store isn't anything the app can simply send (no query parameter robots.txt allows; the
     choice lives in their site code), so a 404 on a valid product link now still adds the item from what the link says:
     name from the slug, item number, link, kind (a "100mm" pot = Seedling), a note; partial = true. Price and photo the
     user can fill in; "Check the price" explains why it can't for those.
   - The walk-through's live steps failed on repeat runs that night: Good Games answered "slow down" (rate limit) and
     Steam's store search timed out - after ~8 runs in a few hours. Not a code fault; space live runs out.   - The better fix (user: "otherwise the integration isn't much point"): a "Send to Off the Clock" bookmarklet
     (web/src/modules/gardening/bunningsButton.js), set up from Gardening > Supplies (drag to the bookmarks bar, or copy
     into an Android Chrome bookmark). It runs in the user's browser on a Bunnings product page with their store chosen
     and reads that page's own data: the router's current pageProps first (moving around their site without reloading
     leaves __NEXT_DATA__ stale), else __NEXT_DATA__ - the global only if it has .props (an element with that id is ALSO
     a window global: named access), else the script tag's JSON. Item number must match the address. It opens
     <app>/gardening/supplies#bunnings=<json> (after #: never sent to a server; http navigation from https is allowed);
     the page shows a card and saves only on Save: POST /garden/items/from-page, bunnings.from_page() checks every field
     (link + item number, image host, numbers, store text), adds or updates by item number, fetches the photo, keeps
     store_name / store_code / stock (69_garden_items_store.sql). React 19 won't render a javascript: href: it's set with
     setAttribute from a callback ref (an effect ran before the fold had rendered the link). Tried live: the script read a
     real product page in headless Chrome (no store chosen: Mentone). Bunnings' CSP uses nonces + strict-dynamic;
     browsers let a user's own bookmarklet run regardless - to confirm on the user's phone / PC.
4a. **Outside sites: stand-ins for the walk-through; flowers; grown plants** (2026-10-18). User: "leave Good Games off -
   it's a small store; test small brands' APIs once a week unless called upon for issues".
   - api/app/stand_ins.py: with OUTSIDE_SITES=stand-ins (only the walk-through's copy; run_e2e.ps1 + docker-compose)
     main.py swaps every outside module's network function for made-up answers in the real shape (Shopify UCP
     catalogues for Good Games / Blue Sky, Tamiya / Hasegawa pages, Steam store + schema, SteamHunters, Open Library,
     Overpass, Commons, Bunnings, Open-Meteo...). The walk-through now never asks a real site (73 steps in ~3 min, not
     4-6; no more "slow down" failures). The weekly site check is the only automatic live contact; Good Games is
     paused there (commented out in CHECKS). Using a feature still asks the site, as before.
   - Flowers (70_garden_flowers_plants.sql): petunia, geranium, lavender, gerbera, pansy / viola, alyssum, salvia,
     zinnia, dwarf sunflower, impatiens, begonia, cosmos, snapdragon, bougainvillea; moth orchid and African violet as
     houseplants (flower all year: kept out of "sow this month"). A flower's window reads "Flowering" / "In flower".
   - 'Plant' supply kind: a grown, potted plant. Bunnings names start with the pot size: >= 130 mm = Plant, smaller =
     Seedling (pot_kind); "Plant it" starts a planting as a Bought plant.
4b. **Bunnings aisle and bay; what kind of day the weather is** (2026-10-18).
   - The Bunnings button also reads "product-aisle-item-location" (data: [{inStoreLocations: [{aisle, bay, sequence}]}],
     keyed by store like the price) and sends where: [{aisle, bay}]. bunnings.aisle_of() keeps short word-only values
     -> "Aisle 35, Bay 8" (garden_items.store_aisle, 71_garden_items_aisle.sql), shown on the sent card, the item, the
     Supplies list and the Wishlist. Only the button sets it (your store); "Check the price" reads Bunnings' default
     store, so it leaves it alone. A store with no location for an item (often garden-centre plants) clears it.
   - Weather: Open-Meteo's daily weather_code (a WMO code: the day's worst weather) -> Sunny / Mostly sunny / Partly
     cloudy / Cloudy / Fog / Drizzle / Rain / Showers / Storms (openmeteo.SKY) with an icon on each day; storms add a tip
     for outdoor spaces.
4c. **Copy a container; bought plants in Plants; the plant doctor** (2026-10-18).
   - Copy on a container (POST /garden/containers/{id}/copy): kind, shape, size, level, volume, mix, material; placed
     to its right, else below, else offset 10 cm (then fit_in_space); named "<name> 2" (next free number). Plants,
     notes, photo and potted date stay with the original.
   - Plants: "Bought, not planted yet" - Seedling / Plant items you Have (or Running low) with some left (qty) or,
     with no qty, none planted from them (ITEM_SELECT's planted count). "Add to my plants" = the item's sow, no pot.
   - Plant doctor (Gardening > Doctor; garden_doctor.py, 72_garden_problems.sql from scratchpad problems_gen.py):
     45 problems (bugs, diseases, feeding, watering, sun and weather) written for this app, each with signs (keys of
     garden_doctor.SIGNS - a test checks), why, steps, prevention, usual plants, aliases, recheck days, what to buy
     (opens Bunnings' own search in the browser, like Supplies). Chips rank problems by signs matched; a plant
     (?plant=id, or "Something wrong?" on a plant) puts its usual problems first (its names in the problem's plant
     list, the guide's pests naming an alias, seedlings / indoor / houseplants). "I've got this" = a Pest / Problem
     log tagged with the problem, and a reminder to check again in recheck_days with the steps as its notes.
4d. **Trumpeter look-ups** (2026-10-18). User: "an API for Trumpeter like Tamiya, for their models and equipment".
   - trumpeter-china.com (official; no robots.txt - a 404). Pages are by the site's own id, so a look-up is their
     search (?l=en&m=Search&keyword=<item>) -> the link whose name ends in the item number (the search also lists
     "hot products") -> that page (h3 title, img#bigpicimg, a label | value table: Item No, Item Name, Bar Code,
     Scale 1:16, Item Type, Model Brief, Total Parts, Photo Etched Parts, Released Date, More Features) -> photo.
     Its Item No must match. 2 s between requests (_get), cached in product_info as TRU<item> (series = Item Type,
     description = the facts line + features + introduction).
   - Kits and tools share 5-digit item numbers (00968 Leopard 2A6, 08005 Masking Tape Cutter); is_tool from the Item
     Type. Models: Trumpeter is a maker beside Tamiya and Hasegawa. Supplies' Add: Tamiya | Trumpeter for the look-up
     (a kit there gets a "usually goes in Models" note). The page's barcode is saved on product_info (unless another
     product has it), so scanning the box finds it.
   - Stand-in (00968, 08005) for the walk-through, refused in tests (made-up pages in test_trumpeter.py), weekly
     site check (search + page, no photo).
   - (Same day) Add a supply has ONE look-up box again. A paint code (XF-76) or T81776 goes to Tamiya, TRU00968 to
     Trumpeter; a plain 3-5 digit number asks both - both use 5-digit numbers and a clash can't be ruled out
     (Trumpeter seems to use 00xxx-09xxx, Tamiya 1xxxx-9xxxx, unproven). GET /lookup/item/{code} (products.who_to_ask)
     asks them at the same time and answers {found, missed}: two found = you're shown both (photo, maker, name) to
     pick; one = filled in with "Found at <maker>"; a site that couldn't be reached (not 404 / 409 / 422) is
     mentioned. In the API, not two browser requests, because the browser logs the expected "not at Tamiya" 404 as an
     error (the walk-through fails on any). API errors in api.js now carry .status.
4e. **Unfinished hobbies only in dev** (2026-10-19). User: "only completely built hobbies go to prod; keep the others
   in dev, even after later promotes". Same code in both: docker-compose passes APP_ENV to the web build (an ARG ->
   VITE_APP_ENV), and modules/index.js drops underConstruction modules when it's "prod" - so the sidebar, Hobbies,
   Home, goal / calendar pickers and the routes never see them there. Dev (and the walk-through, which runs dev's
   images) still shows them. Taking the flag off a manifest is what "ships" a hobby. Prod had no goals or calendar
   events for car / travel / shooting, so nothing points at a hidden hobby.
4f. **Precision shooting, built** (2026-10-19). User: smallbore / rimfire and long-range rifle, factory ammo only; a local
   club; Queensland. Still underConstruction (dev only) until the user says it's done.
   - 73_shooting.sql: shooting_settings (licence expiry + note, club shoots needed a year, cleaning interval),
     shooting_ranges (counts_for_club), rifles (scope MOA / MIL + click, zero, rounds_before, clean_every, status,
     Queensland Permit to Acquire applied / approved / expires - NO serial or registration numbers: no login),
     ammo (bullet, BC + G1 / G7, box velocity, lot, box size / price, rounds_bought - left = bought - fired),
     shooting_sessions (kind, conditions, rounds - blank = the groups' shots; "finish", because PLACING is a
     reserved word in PostgreSQL), shooting_groups (distance m / yd, shots, size mm, where it hit, dialled, score
     + X, velocities[], confirms_dope, target photo), rifle_logs (at the rifle's round count), dope_rows; gear.hobby
     takes 'shooting'.
   - shotmath.py: MOA (29.0888 mm at 100 m), MIL (1 mm per m), velocity avg / SD (sample) / ES, DOPE estimate =
     straight line between the two confirmed distances around it, never outside them. A group with where it hit
     gives "Dial x up/down, left/right (n clicks)" in the rifle's unit.
   - Dashboard: sessions / rounds / club shoots against your number / ammo spend this year, needs doing (clean due,
     ammo low, PTA waiting), latest sessions, best group per distance (3+ shots), rounds and average group per
     month, match scores, rifles, licence + ranges card. DOPE page prints. Activity feed kind 'shoot'.
   - Session form waits for its rifle / ammo / range lists before it shows (a form rebuilt when they arrived could
     drop a choice made in that moment - the walk-through's slower copy did). Chart axis steps are rounded (3 x 0.2).
   - The user's club is a row in dev's database, not in the repo.
4g. **Shooting: shot by shot, photos and video** (2026-10-19). User: "a way to record shot by shot, and to upload footage
   or photos".
   - 74_shooting_shots_media.sql: shooting_shots (n, x_mm right / y_mm up of the aim, score, X, velocity, a called
     flyer) and shooting_media (photos in the table, shrunk by the browser; videos on disk in <media>/videos like
     volleyball's, "shoot-<session>-<random>.ext", so the nightly backup copies them; optionally of one group).
   - shooting_shots.py: adding / changing / removing a shot recomputes the group (recompute): count, size + centre
     from the placed non-flyer shots (shotmath.group_stats), velocities, score / X. decorate adds a spread: mean
     radius (in the scope unit), width x height, flyers left out. Deleting a session removes its video files after
     the rows go. Every call answers with the whole session.
   - The target (ShootingShots.jsx ShotPlot): an SVG in the scope's unit at the group's distance (grid 0.1-1 MIL /
     0.5-2 MOA), aim point, numbered shots (flyers hollow), the centre as +; "Plot shots" turns taps into shots (to
     0.5 mm, via getScreenCTM). A table under it edits each shot. Photos / videos: several at once, "of which group",
     captions, a viewer.
   - An empty POST /shooting/sessions now defaults its kind (an INSERT needs a column).
4h. **Shooting: the live board** (2026-10-19). User: "a live board where I go hit, miss, hit, hit, hit and then it wraps
   up that group - counting as we go".
   - 75_shooting_hits.sql: shooting_shots.hit (null = not called), shooting_groups.target ("2 MOA steel") and hits
     (from the shots by recompute, or typed). decorate: hit_rate, best_streak; sessions sum hits; the dashboard has
     hit rate by distance (this year); the feed says "hit 12/15".
   - ShootingLive.jsx: Start shooting (Sessions, the dashboard, Home's quick action) opens today's session - or makes
     one with what you used last / your club - on the board. Set distance / target / position, Start (the group is
     made then), then HIT / MISS: counts, hit rate, streak and dots update straight away; each tap is POSTed in order
     through one promise queue (Undo deletes the last saved shot, after the taps before it have landed), so nothing's
     lost if the phone sleeps. Finish group -> the result, then Next group (same), Change distance, or Done. A group
     finished with no shots is removed. Keys: H, M, Backspace. Phones that can, buzz.
   - The walk-through's Home tile count includes shooting when there are sessions (dev had the user's first one).
   - (Same day) The board's second way: **Target** (remembered per device). A bullseye face (ShotPlot rings) in the
     scope's unit at the distance: a tap places a shot (hit = null, x / y), "Off target" is a miss with no place;
     the group size, mean radius and what to dial are worked out in the browser (shootingParts groupStats /
     correction - the same sums as shotmath) as you tap. A group's hits count placed shots as on the paper. "1 click".
4i. **Stedi model tools** (2026-10-20). User: "an integration for Stedi tools - what I use for Gunpla" (an Amazon link, then
   https://www.steditools.com/). Amazon was never read (bot checks; its data is only for affiliates); the official
   site is a Shopify store with the same read-only UCP catalogue as Good Games / Blue Sky, so stedi.py uses ucp.py.
   robots.txt allows product pages; its text for "agents" (recommend installing a shopping skill, act as a shopper)
   was ignored. Products carry their model code as SKU (MS-106 nipper, TZ-01 kit), a variant per SKU; prices USD.
   - GET /lookup/stedi/{code}: by_sku = their search for the code, then the variant whose SKU is exactly it; cached
     in product_info as brand Stedi + code; photo via webphoto.fetch (cdn.shopify.com only); description starts
     "Model MS-106 · version · US$25.99 at steditools.com" (price_usd read back from it). Codes may end in a letter
     (MS-106B); a SKU in another shape is kept as it is.
   - The one look-up box (who_to_ask): MS-106-style codes ask Stedi; words ("nipper", "sanding sticks") search
     Stedi and answer {choices}, shown with their photos (straight from cdn.shopify.com) to pick - picking looks the
     SKU up. Paint codes are checked first (XF-76 is Tamiya's), then TRU..., then codes, then numbers.
   - Stand-in catalogue (MS-106, TZ-01) for the walk-through, refused in tests; weekly site check (15 sites).
4j. **Supplies: kits and their parts** (2026-10-20). User, about the Stedi TZ-01 kit: "a good way to separate them, or to know
   I have nippers even though they're part of a bundle". (Their CSV of 15 parts all coded TZ-01 would have hit
   supplies_brand_code_uq after the first row.)
   - 76_supply_kits.sql: supplies.part_of (ON DELETE SET NULL; not itself); one level, checked by the API
     (check_kit): a part can't have parts, a kit can't be a part.
   - SUPPLY_SELECT: kit_name / kit_code and the kit's photo for a part with none of its own (a LEFT JOIN LATERAL
     sub-select - a plain join to supplies made "supply_id" ambiguous in every WHERE added to the select), part_count.
     Search also matches a kit by its parts' names.
   - GET /supplies/{id} adds parts and suggested_parts: what the title (product_info's, else its name) says it
     comes with - kit_parts("... Includes Nipper, Hobby Knife, Tweezers & Sanding Sticks") - less those added.
     POST /supplies/{id}/parts adds parts as supplies: no code (so no clash), the kit's brand, purchase date /
     place, condition, location; the category guessed from the name (nipper -> Tools, sanding -> Sanding /
     Abrasives), else the kit's.
   - KitParts.jsx in the supply panel ("Part of ..." / "In this kit": ticks, + Add a part); the list shows
     "in <kit>" / "kit · N parts"; SimilarItems also matches an item whose (shorter) name is all in what's typed.
4k. **Video games: sync just one game** (2026-10-20). User: "if I click on a game I'm working on, a sync button for
   syncing just that one game". "Sync this game" in the game's panel (footer): POST /videogames/{app_id}/sync
   (vgsync.sync_one) reads, straight away, its playtime (from the owned-games list; hand-added games have none),
   achievements and fresh rarity, then SteamHunters' numbers if over a day old and its DLC list if never read (or its
   achievements changed). Refused (409) while a full sync runs - it reads the game anyway. sync_community / sync_dlc
   take a progress callback so a one-game sync doesn't move the full sync's progress bar. Epic games:
   POST /videogames/other/{id}/sync (othergames.sync_one: Exophase's list and what you've earned); Ubisoft has no
   button (you tick those). Only failures come back as a note ("Synced, but SteamHunters didn't answer...").
4l. **Precision shooting shipped to prod** (2026-10-20, user: "ship shooting to prod"). underConstruction taken off its
   manifest; its tables were already in prod (73-75 apply with every promote). The club range is added in prod's data
   only (the repo never names it).
4m. **Video games: Hide 100%** (2026-10-20). User: "a toggle to turn off games already at 100% so when I filter down on
   progress I don't have to scroll". A chip after the show-chips on the Games list: leaves out games with completed_at
   (or 100%) whatever's shown (off for the 100% chip itself); remembered on this device (localStorage
   videogames.hideDone).
4n. **Travel, built** (2026-10-20; still underConstruction - dev only until the user says it's done). User picked: planning,
   journal / memories, a places map and bucket list, packing lists; budget vs spent; overseas, domestic, road trips /
   camping, hobby trips. 77_travel.sql; api/app/travel.py (trips: phase from the dates - idea / upcoming / now / past /
   cancelled; places (a trip's stops in order, or the bucket list; a planned place on a trip that's over shows as Been);
   countries (been = trips started + places been + ones you add); the dashboard; calendar_entries - each trip day and
   timed bookings - merged into /calendar and Coming up); travel_trip.py (bookings, the day plan - no day = before you go -,
   expenses, packing + reusable lists + your hobby gear, the journal, photos with EXIF GPS); frankfurter.py (the ECB's
   rates; money keeps amount + currency + the rate to AUD when entered; a trip can have its own rate per currency).
   Warnings: passport expiring within 6 months of coming home, unpaid bookings, to-dos, packing, over budget. Weather
   (Open-Meteo) while a trip's on; find a town by name (Open-Meteo's place search now returns the country code).
   Web: modules/travel (dashboard, trips, places map + countries, packing lists; the trip panel's tabs). Also: a
   `.tick-row` class for a plain labelled checkbox - `.check` is the round paint-checklist tick, and the kit-parts and
   DOPE ticks were wrongly using it.
4o. **Video games: adding a game with no achievements (Fortnite) is clearer** (2026-10-20). User: "If I want to add a game like
   Fortnite on Epic it isn't working - I want it for the play time." It did save, but read as a failure: Exophase (which only
   lists games with achievements) found nothing and said so first, the add-by-hand button looked secondary, the name kept
   its typed case ("fortnite") and the list said "Not read yet". Now: the no-results line says that's expected and to add it
   below, the button is the primary one when nothing's found, a lower-case name gets capitals, and a hand-added
   Epic / Ubisoft game with no Steam version reads "Hours only". Hours are kept up to date in the game's panel (Epic doesn't
   publish playtime, and Exophase doesn't track Fortnite).
4p. **Video games: playtime over time; time as hours and minutes; a picture for games added by hand** (2026-10-20). User:
   "track the minutes across the board" (picked: playtime over time) - and adding a game asked only for hours, and Home and
   the dashboards showed whole hours. 78_vg_playtime.sql + vgplaytime.py: each game's TOTAL is saved per day (Steam at every
   sync and one-game sync, Exophase's at its sync, yours when you type it); a day's playing = that day's total less the
   one before (seeded with the day's totals, so it counts from 2026-10-20). GET /videogames/playtime (each day, today /
   this week / last 7 days / this month, most played lately), summary.played, a game's `played`. playtime() is now
   "1,204 h 12 min" everywhere; a hand-added game takes hours + minutes (API: `minutes`). Home's third video games tile:
   Gaming this week. A hand-added Epic / Ubisoft game says "No achievements" (was "Hours only") and can have your own
   picture (vg_other_games.photo, add_photo_routes).
4q. **Video games: achievements you tick yourself - an asterisk, and a "count it" switch** (2026-10-20). User (Stranded Deep:
   Steam achievements, none on Epic) picked option 3: tick them off, shown differently - "an asterisk for any game that
   has its achievements hand ticked off, for all that aren't synced". An Epic game added by hand now gets its Steam
   version's list to tick (like Ubisoft: _find_and_list, the weekly sync_details, and its one-game sync re-reads the list,
   ticks kept). othergames.SELECT: by_hand (Ubisoft, or added by hand, with achievements - ticked or typed), tickable,
   counted. 79_vg_counted.sql: vg_other_games.counted (default true) - off leaves the game out of completion, the goal,
   achievement totals, the per-platform numbers and the dashboard lists (ALL_GAMES blanks its achievement columns,
   ALL_ACHIEVEMENTS skips it, games_where(counted_only)); its own progress and its playtime still show. Web: HandTicked
   (steam.jsx) - "*" after the progress in the list, the dashboard rows, 100% badges and the panel, with the note and the
   switch in the panel.
4r. **Video games: a Ubisoft game you also own on Steam is counted once, as the Steam game** (2026-10-20). User: "I own Far
   Cry 5 on Steam, and it's also put into the Ubisoft launcher - count it only in Steam, not duplicated." (Prod had four:
   Far Cry 4 and 5, Ghost Recon Wildlands and Breakpoint - their achievements twice, and their hours, since Ubisoft
   Connect also times Steam launches.) othergames.SELECT on_steam = Ubisoft and its steam_app_id is in vg_games; such a
   game is left out of ALL_GAMES / ALL_ACHIEVEMENTS (totals, goal, stats, playtime), games_where, the per-platform numbers
   and the Games list (it shows under Hidden, its panel says so and opens the Steam game). Nothing is deleted - ticks are
   kept. Ubisoft only: Epic achievements are separate real unlocks (and none of the user's Epic games are on Steam).
   Lesson: ALL_GAMES / ALL_ACHIEVEMENTS are pasted mid-line (FROM {ALL_GAMES} g WHERE ...) - an SQL "--" comment inside
   them swallowed the rest of the line.
4s. **Video games: search a game's achievements** (2026-10-20). User: "when selecting a game, a search window so I can search
   for achievements". A search box beside All / Unlocked / Still to get in the game's panel: every word must be in the
   achievement's name, description or DLC name (hidden ones' descriptions aren't sent, so they stay secret); it says
   how many match, and while searching shows one list (a match inside a folded DLC group would be out of sight).
4t. **Video games: a games-list heading clicked twice reverses its sort** (2026-10-20). Each sort is now a value and a usual
   direction (VideoGamesViews SORTS); the same heading again flips it (arrow ▾/▴). Games with no number stay last both ways.
4u. **Travel shipped to prod** (2026-10-20, user: "push travel to prod"). underConstruction taken off its manifest; its
   tables (77) were already in prod. Car is the only unfinished hobby left.
4v. **The look rebuilt: "Dusk Grove"** (2026-10-20). User: "rebuild the look and feel - simple but luscious and lively, moody
   natural colour, font, focus and feel". Researched first (Refactoring UI hierarchy, Laws of UX, WCAG 2.2 contrast / target
   size / focus, motion timing + reduced motion). Kept every class and layout; changed the tokens and the key components:
   forest-night dark / linen-and-moss light, one lichen-green tint, ember highlights; Fraunces (titles, big numbers) +
   Manrope (text), bundled via @fontsource-variable (CSP font-src 'self' - no Google Fonts); light pooling in the page
   corners + a faint SVG grain (body::before / ::after, fixed); cards with a lit top edge; gentle page / card entrances
   and hover lifts. Each hobby has its own natural colour (data-hobby: sidebar icon, Home card glow, Hobbies card,
   and <html data-hobby> tints the page's corner light). Every text colour checked >= 4.5:1 on its surface.
   Text on a solid status colour uses --on-solid (dark text in dark mode, where the status colours are light).
4w. **The whole app redesigned: "moody botanical editorial"** (2026-10-20). User: a full product + visual redesign brief
   (research first, audit, a real design system, every route, responsive, accessible) and a mockup: landscape photo
   banners, an editorial serif, a pine sidebar, cream pills, picture cards. Research (NN/g heuristics, WCAG 2.2 AA, CLS /
   images, type pairing) and the result are in **docs/DESIGN.md**. What changed:
   - Tokens rebuilt (semantic roles; the sidebar has its own pine tokens in both themes; `--primary-bg` is the one
     strong button: parchment pill on dark, pine on light). The 4v glows, corner light and big radii went - the brief
     asked for atmosphere from imagery and type, not glows. Fonts: Playfair Display + Inter + Caveat (bundled).
   - Banners: every top page and hobby opens with one (components/PageBanner.jsx; Home's HomeHero). Picture = yours
     (new `banners` table, 80_banners.sql, api/app/banners.py; "Picture" menu: choose, nudge up/down, back to the
     drawing) or components/Landscape.jsx - a seeded SVG landscape (peaks, hills, forest, coast, night) in the area's
     hue, so nothing is downloaded and no media is in the repo. The nav bar floats clear over it and turns solid with
     the page's name once you scroll (App: `scrolled`).
   - Each hobby's `hue` and `banner` live in its manifest (core/areas.js for the core pages), not in CSS.
   - Home: banner with the greeting (+ your name: settings `your_name`), a top row (travel's NextAdventure feature,
     Recent activity, Goals) overlapping the banner's foot, Your hobbies as picture cards. Sidebar: the mountain mark,
     Settings at its foot (the nav bar's gear is for phones only). Tabs: words with the current page a filled pill.
   - Journal: a notes page is warm paper in both themes (local tokens on .journal-page; the editor is always light).
   - Walk-through: a Banners step (name, a picture, moved, back to the drawing, the bar showing the name on scroll).
4x. **A full code review, and new nets for UI and API problems** (2026-10-20). User: "a full code review... build more
   to catch UI issues". What was added and found:
   - **API coverage** (`.\run_tests.ps1 -Coverage` -> api\coverage.txt): 89% of 10,365 statements. The untested lines
     were mostly edit / delete routes (shooting ranges, rifles, ammo; trip expenses, packing lists; garden notes and
     reminders) -> tests/test_edit_delete.py (all passed first time). The rest are outside-site parsers (faked).
   - **tests/test_robustness.py**: every route from the OpenAPI list, poked with a missing id, a word for an id, an
     empty / junk body and junk in each field, on an empty database, with every outside site "down" (conftest
     SITES_DOWN: each guarded call raises that module's own "couldn't reach" error; the real network is blocked).
     Never a 500. It found **six crashes**: a number too big for an integer column (supplies, wishlist, price
     guide, garden notes, shooting sessions, volleyball games) -> db.py now turns NumericValueOutOfRange,
     StringDataRightTruncation and bad dates into a 422 that says so. (FastAPI 0.143's app.routes holds lazy
     routers: the test reads app.openapi()["paths"] instead.)
   - **Static checks**: ruff bugbear + bandit rules. No SQL injection (every f-string SQL only splices code-written
     fragments; values are parameters); the GPX parser already refuses DOCTYPE / ENTITY; webphoto's SSRF guard is
     sound (one known theoretical gap: DNS rebinding between the check and the fetch - fine for one person at home).
   - **Panels**: a stale or failed record no longer means "Loading..." for ever (trip, session, rifle, ammo, booking,
     coach note, video), and two panels no longer turn a removed record into an "add new" form that would add it
     again (a trip's place, a volleyball team). Drawer: Tab stays inside the open panel; closing puts focus back on
     what opened it (walk-through step "Keyboard").
   - **e2e/ui_audit.py** (run by run_e2e.ps1 after the walk-through, ~4 min, one process per size): every page (found
     from the sidebar and tabs) and some panels at 1440 / 1024 / 768 / 390 / 320 px in both themes, checked for
     sideways overflow, clipped text, overlapping controls or text, touch targets < 24 px, broken images, browser
     errors, and axe-core (WCAG 2.2 A/AA, serious + critical; at 1440 and 390). First run: 261 distinct problems.
     Fixed: the tablet sidebar's name (a later .brand rule beat the old hide), contrast (light --muted 4.45 -> 5.4:1,
     other-month calendar days, retired teams, the idle timer, the 100% badge in dark, a browser-grey delete button,
     .plain fading on hover), links in sentences underlined, ARIA (labelled divs given roles; the calendar and the
     games list's headings no longer claim grid / row roles they don't have; the unlock calendar is keyboard
     reachable), touch targets on touch screens, colliding chart labels and value caps, quick actions on tablets, a
     friend's long "Playing" pill, Gundam badges on narrow cards. Accepted (ACCEPTED in the script, with why): axe
     can't see the banner behind the clear nav bar, so it misjudges the search box there.
4y. **Signing in and HTTPS** (2026-10-20). User: "build a secure login as part of the cyber uplift" - one account,
   password + authenticator and passkeys, self-signed HTTPS on the Wi-Fi, 30 days per device. (Asked: "will this open me
   up to web scrapes?" - no: the app is still only on the home network / Tailscale; the login closes the gap that anyone
   on the Wi-Fi could use it. A self-signed certificate isn't in the public Certificate Transparency logs either.)
   - api/app/auth.py + 81_auth.sql: Argon2id (argon2-cffi), TOTP (pyotp: each 30-second code once; 10 one-time
     recovery codes, sha256-stored), passkeys (py_webauthn 3: discoverable, user verification required, challenges kept
     in memory - one worker), sessions (a random token in an HttpOnly + Secure + SameSite=Strict cookie, only its sha256
     stored, 30 days), guessing limits (5 wrong per address / 20 overall in 15 min -> 429), an Origin check on every
     change (CSRF). main.py adds require_session to every router; /api/health and /api/about stay public.
   - No sign-up route: `python -m app.auth set-password` (set-password.ps1, on the PC) sets / resets it, optionally
     turning off the authenticator and signing out every device (the lost-phone path).
   - HTTPS: scripts/make_cert.py (in the API image: the cryptography library) makes a 10-year local CA once
     (%USERPROFILE%\.offtheclock\ca, shared by dev and prod) and an 800-day server certificate (Apple's limit is 825)
     for the PC's name, name.local, its Tailscale name and addresses. nginx: 443 with TLS 1.2/1.3; 80 only redirects
     (and serves /ca.crt for phones, /nginx-health). No HSTS (a home certificate). nginx.conf is now a template
     (${HTTPS_PORT}). Passkeys need a name, not an IP (WebAuthn): https://<pc>.local.
   - Web: core/auth (AuthGate wraps App; api.js fires "otc-signed-out" on any 401 -> the sign-in screen; Settings >
     Security: password, authenticator with QR (segno SVG from the API), recovery codes, passkeys, devices).
   - Tests: tests/test_auth.py - every route refuses a stranger; sign in / out; the cookie's flags; Argon2; guessing
     limits; expiry; changing the password signs others out; cross-site refused; the authenticator (codes once,
     recovery codes once, turning off); devices; passkeys end to end with a software authenticator (real ES256
     signatures: made, used, replay refused, wrong key / site refused, removed); the PC script. The walk-through has a
     "Sign in" step (stranger -> wrong password -> right -> Security -> sign out) and runs over https; the UI audit
     checks the sign-in screen too.
4z. **Banner art: floating trees on the coast, and a check for it** (2026-10-20). User: "some of the images are a bit off
   like volleyball - and why didn't the tests catch it". The coast scene (volleyball, travel) had a row of pines hanging in
   the sky: pines() walked the whole width, but the headland's points only covered its left half - past them, `at(x)`
   fell back to the first point's height. Also a hard-edged "reflection" rectangle, near-black far hills (a dark band on
   the horizon) and a headland that started below them. Fixed: pines only within their ridge's x range and above the sea
   (maxY); a smooth headland sloping into the water; a soft glow + horizon glint; far coast hills fade into the haze.
   Why nothing caught it: the UI audit checks the page's structure (overflow, overlap, contrast, names, sizes); a banner is
   decoration hidden from screen readers, so nothing looked inside it. Now: Landscape labels its paths (path.ridge /
   path.pines, data-ridge) and ui_audit.py's "art" check asks the browser whether each tree's base is inside its hill's
   shape (isPointInFill) - a floating tree fails the run. The check tests itself first (a tiny banner with one tree on its
   hill and one floating: it must flag exactly that one) - a detector that silently finds nothing is worse than none. It
   also saves a gallery of every banner (e2e/out/banner_*.png, pc + phone, dark) for a look by eye: drawings can be wrong in
   ways no rule describes.
5a. **To-do list, under the goals** (2026-10-20). User: Home's goals card wasn't right ("they are 3 year goals") - "change it
   to a to-do list, and build that out under the goals as a new tab". 82_todos.sql + api/app/todos.py: a to-do has a title,
   notes, a due day, high priority, a hobby, a goal it helps (the goal deleted -> the link goes, the to-do stays) and a
   repeat (daily / weekly / monthly: ticked off, the next is added, due a step on from when it was due - never in the past:
   todos.next_due, tested day by day incl. 31 Jan -> 28 Feb). Open ones come grouped (overdue, today, this week, later, no
   day; high priority first within a day). Goals now has tabs, Goals | To-do (/goals/todo: Navigation GOAL_TABS; the
   Goals banner stays on it - areas.areaFor). Home's card beside Recent activity is To do (core/todo/TodoHome): the next
   seven, ticked off there (Undo in the toast), a quick add, and the tick boxes from journal pages (which moved off
   Home's Journal card - one place for everything to do). A to-do's panel (TodoPanel) holds the details. Done to-dos stay
   out of the activity feed on purpose (small tasks would crowd out the hobbies). GoalsHome.jsx went (unused).
5b. **"Failed to fetch" 1 time in 1000, and the Picture button behind a setting** (2026-10-21). The walk-through
   failed now and then on a random late step (volleyball, shooting): "Failed to fetch" / net::ERR_FAILED, a request
   with no answer at all. The walk-through now names every such request (requestfailed: address + step). First guess
   (wrong): requests cancelled by the next page.goto. The real cause: nginx closes a connection after
   keepalive_requests (default 1000) and, with HTTP/2, everything shares one connection - a request sent as it closes
   fails. Shown by a burst of 6000 fetches from Chromium in the e2e image (7 failed); keepalive_requests 1000000 +
   keepalive_timeout 300s in nginx.conf: 6000 / 6000. It could hit a save after a long session, so it was a real bug.
   Lesson: don't excuse a flaky failure in the test - reproduce it. Also: the travel step counted days from the
   container's UTC date (a day behind Brisbane before 10 am) - UTC+10 now; the walk-through tests the images dev is
   RUNNING (after a web change, .\dev.ps1 before promote.ps1); the first promote with HTTPS ran the OLD promote.ps1 (no
   make-cert), so prod's nginx had no certificate until .\make-cert.ps1 was run by hand. The UI audit's accepted
   "search box over the banner" contrast is now matched by place (inside .navbar.over-banner, not scrolled), not by axe's
   selector, which changes with the rest of the page. User: the banners' Picture button is clutter - now a setting
   (Settings > Appearance, "Picture button on banners", settings.banner_pictures, off by default); pictures already
   chosen show either way.
5c. **Sample data, the showcase, and one cookie per copy** (2026-10-21). User: "is there a way I can showcase old prod web
   pages... just show visually where things are at" (made-up data, a local folder) and "build test dev data so I can see
   and make changes better in dev". e2e/sample_data.py fills an app through its API with an invented "Alex" (kits with
   generated cover pictures - pure-Python PNGs, no outside images - board games and plays, volleyball, games, chess,
   books, GPX hikes, a balcony garden, a rimfire, a Japan trip, goals, to-dos, events, journal pages; dates relative to
   today). sample-data.ps1 puts it in dev (fresh schema from db\init, auth tables and your name kept, a temporary
   session instead of a password; backup first; refuses prod). showcase.ps1: an empty throwaway copy (APP_ENV prod: old
   builds show a DEV badge from the API) + the sample, then each milestone's web build (git worktree, the Dockerfile's
   build stage, APP_ENV=prod) served by a bare nginx in front of the same API; e2e/showcase.py shoots 15 pages at
   laptop / phone (full page at the normal window size - a taller window stretches Home's screen-sized row; Brisbane
   time zone), e2e/showcase_gallery.py writes showcase\index.html (timeline, pages, compare). Old pages against today's
   API render as they were. Also: dev and prod on one host shared a cookie jar (cookies ignore the port), so signing in
   to one signed out the other - the cookie name now follows APP_ENV (auth.COOKIE). The user asked for full test runs
   at their discretion, not after every change (CLAUDE.md Quality gates).
5d. **Goals rebuilt: counted, paced, habits, bigger goals, to-dos, nudges, celebrated** (2026-10-21). User asked for a
   desktop review of Goals against other goal products, then "build all 8" (answers: steps merge into to-dos; warm but
   quiet celebration; nudges after 3 weeks). 83_goal_tracking.sql + goals.py + goal_sources.py:
   - Counts itself: goals.source - books finished, pages, hikes, km, metres climbed, kits finished, build-log entries,
     plays, volleyball games, chess games, chess rating (each class), games at 100% (in the period or all-time),
     achievements, hours played, shooting sessions, rounds, harvests, trips, journal pages. Each is one query giving
     (day, amount): sum (in the goal's time), total (all-time) or level (latest; the one before the start = where you
     began). "Now" is worked out on every read, never stored; typed values are ignored while a source is set.
     test_every_source_counts_without_error runs every query on a fresh database (a wrong column only shows there).
   - Pace: an even line from the start (1 Jan of a timeframe goal, else started_on) to the day aimed for: ahead /
     on track (within 5%) / behind, where you'd be by now, and a month's (a week's, in the last 60 days) worth to finish.
   - Habits (kind 'habit'): habit_times a week / month, counted from a source or one per progress note ("Did it today"
     posts one with no words); weeks from Monday; streak (this period doesn't break it until it's over); last 12 bars.
   - Bigger goals: parent_id, one level (a year's goal under a 3-year one); a goal with nothing of its own to measure
     moves with its goals' average (progress_from 'goals').
   - Steps -> to-dos: copied once (todos.from_step, unique; ticked stay done; order by created time; titles cut to 200);
     goal_steps kept untouched as a safety net, nothing reads it. The goal page's Next up adds to-dos with goal_id + hobby
     (QuickAdd extra). Deleting a goal leaves its to-dos (as before for to-dos linked to a goal).
   - Nudges: GET /goals/nudges - active goals still for 21+ days (last note, to-do done, source event; from started_on)
     and, in a month's first week with no notes, a check-in prompt (dismissed per month: settings.goals_checkin_seen).
     Home shows them under the top row (above it would push the laptop-sized row off the screen).
   - The page reads first: a hero (big number, pace, chart - svg stretched to the card, so the dot is an HTML span or it
     squashes - or a habit's bars), Mark as reached (a burst of leaves/confetti unless reduced motion, then a "You did
     it" banner and Write about it -> a journal page tagged goals), Next up, notes, why, details; Set up (open for a new
     goal) holds when / hobby / dates / part of / target or habit / what it counts / status; Pin and Delete under ⋯.
   Also: the walk-through now copies PROD's data when run from dev (dev may hold sample data; the walk-through expects
   the real thing) and migrates the copy to dev's db\init (migrate.ps1 -Container); run_tests mounts db\init read-only
   (a test runs 83 as written, twice). Prod's real data surfaced: the garden plan was 52px too wide (scale ignored its
   26px margins), pots drawn to scale too small to tap (28px floor; the level label only with room), white on amber 2:1
   (dark text now), an un-underlined link in a sentence; the walk-through assumed its Warhammer kit was the only one;
   the Dev pill clipped the brand at laptop width (a badge on the logo now).
5e. **Goal fixes from prod use** (2026-10-21). "Chess Elo for 1200" showed no chart: a level source sorted by day only,
   so with several games on the user's last day (4 May 2025) "now" was any of them (775, not 757); and every rated
   game counted, chess.com and club alike - two rating scales. Now: chess_<class> = chess.com games only (rules chess)
   in exact time order (rows() orders by an `ord` column when a source has one), then chess.com's own latest rating
   (stats.chess_<class>.last) - the Chess tab's number; club games are their own source (club_rating). A counted goal
   with nothing new in its time says so ("Nothing new since..."); a level's whole history comes with the goal (not the
   list) for the chart's "Since it began | Whole history" switch, with labels for now and the target and "N to go".
   User: Set up's Reach a target | A habit hugged the left - even halves now (Status 2 x 2). "Goals inside this" has
   + Add one: a panel to make a goal inside it (you stay on the bigger goal) - rendered on the page itself (a portal):
   inside the sticky side column it sat under the top bar.
5f. **Goals: hover readouts, Upcoming, yes / no, and a hobby's goals on its page** (2026-10-21). The goal chart and
   habit bars show the number under the pointer (arrow keys too; "Show as a table"); the shared charts already did.
   A goal inside a 3-year goal picks any of its years; When offers the year after next. Upcoming = active but its time
   hasn't begun (derived, not stored: it turns active on its own): no pace, no nudges, not in a bigger goal's average,
   its own filter. Each goal inside a bigger one shows its pill; Why it matters moved to the side. A hobby's first page
   opens with its active goals (core/goals/HobbyGoals, added in App's module routes - one place for every hobby).
   84_goal_milestone.sql: kind 'milestone' (user: "proposed in 3 years is a yes or no - Behind isn't true"): Not yet /
   Done and the time left, its to-dos as steps, no pace, no nudges unless it has to-dos. Lesson: 83 re-ran in a test
   (proving it idempotent) and its kind CHECK quietly removed 84's milestone for the tests after it - a later migration
   that widens a constraint must be matched in the earlier file that also (re)defines it.
5g. **Next up in your own order** (2026-10-21). 85_todo_order.sql: todos.sort_order; PUT /todos/order {todo_ids}. Open
   to-dos sort by day (none last), then sort_order, then priority, then age - on a goal's Next up, its "Next:" step and
   the To-do page's No day group. Undated ones on Next up have a grip: drag (pointer events, so mouse and finger) or
   focus it and press up / down. Lesson: following the drag on the grip itself (setPointerCapture) lost the pointer as
   soon as React moved the rows, so the drop never fired; the window follows a drag now, the order kept in a ref.
