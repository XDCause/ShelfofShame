# Off the Clock - build history

Everything built, in order, with the reasons and the lessons at the time (moved out of CLAUDE.md on 2026-10-16 so
the notes Claude reads first stay short). Newest at the bottom. **Entries 1 to 3zzs (2026-10-11 to 10-16) are in
[HISTORY-early.md](HISTORY-early.md)** - the first week, the first hobbies, and lessons like barcodes (3d), the
database pool (3z) and the first check-overs (3zt, 3zw). Search both before changing something old.

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
5h. **Banners and the journal grows** (2026-10-21).
   - Banners: every page's banner is one height, so its name sits in the same spot everywhere; a page without tabs puts
     its search row where the tabs sit (frosted like them; Journal, Supplies on PCs). New drawn extras, all natural
     (user: no buildings): trees, moon, rays, meadow, rainbow, and a mesa scene (Shooting); Chess, Gardening and Supplies
     got their own looks. Journal's All chip now clears the mood too. A notes page is a whole sheet (to the screen's foot).
   - The journal, from a scan of Day One, Apple Journal, Notion and reMarkable (user picked all but voice notes and AI):
     tabs Pages | Calendar | Map | Insights. 86_journal_more.sql: journal_notebooks, journal_templates; pages get
     notebook_id, place (name, lat, lon), weather (JSONB), paper (plain / lined / grid / dot), private.
     api/app/journal_more.py (router before journal's): on-this-day (earlier years' pages + what you did), today (the
     activity feed's day, for "Write about today"), calendar (+ streaks: today or yesterday back, and the longest),
     insights (weekly mood, mood on each hobby's days vs usual - 3 mood days needed - mood words), review (a week /
     month by hobby, goals), notebooks, templates, weather (openmeteo.day_weather: their forecast API keeps 92 days;
     the page's place, else Gardening's "where you are"), places (the map), export (print).
   - Web: core/journal/blocks.js (BlockNote blocks in code, built-in templates, prompts, Today / review pages),
     JournalExtras.jsx (Today, On this day - also on Home's journal card -, Templates menu, notebooks, place, weather,
     prompt), JournalCalendar / JournalMap (TravelMap with a legend prop) / JournalInsights / JournalPrint (the browser's
     print -> PDF; blocks rendered as plain HTML). Private pages: out of the list (unless the Private chip), activity,
     mentions, On this day, the map and export (unless asked).
   - Lessons: stock lines ("Added XF-1") swamped Today and the review - supplies aren't something to write about. A
     review says "Played @Catan" about days already logged, and the page offered "Log a play?" (a second play): pages
     tagged review make no suggestions.
5i. **The calendar grows** (2026-10-21; from a scan of Google / Apple Calendar, Fantastical, Notion Calendar, Sunsama,
   TimeTree - user picked all but phone sync / import / reminders).
   - 87_calendar_more.sql: repeats + monthly, monthly_nth (2nd Saturday; 5th = last), yearly (29 Feb -> 28th), weekdays
     (repeat_days, 0 = Mon) with repeat_every; countdown, lat / lon, checklist JSONB; todos.plan_on / plan_time /
     plan_minutes (time-blocking). calendar.days_of walks day by day through on_day(); /calendar also returns todos
     (due or planned), goals ending (target_date) and holidays. api/app/holidays.py: Queensland's public holidays from the
     rules (Easter by Meeus, weekend substitutes, Ekka = the Wednesday 10-16 Aug) - no outside source.
   - api/app/calendar_more.py: parse (quick add in plain words: days, dates, times and ranges, "for 2 hours", repeats,
     "until", "at <place>", hobby from keywords; tested on 9 phrases), search, countdowns, weather (openmeteo.long_forecast,
     16 days, an hour's cache; the event's place else Gardening's home), balance (planned minutes vs each hobby's logged
     minutes / days), year, bring (gear / rifles + ammo / packing lists), move (one day of a repeating event = skip +
     one-off copy).
   - Web: CalendarPage (Month / Week / Agenda / Year, Show ▾ layers + hobbies remembered per device, drag events and
     to-dos to a day), CalendarViews (Week's hour grid with lanes, drag to a time; Agenda; Year heatmap by activity or
     mood; To plan tray), calendarParts (quick add, search, countdowns - also on Home's Coming up -, balance, Log it:
     volleyball / board games / shooting open their log for the day, others their page; "Logged ✓" when that hobby's
     log has the day), EventPanel (repeat kinds, weekday picks, place for the weather, countdown, What to bring).
   - Fixed on the way: Goals' "Hours played" summed vg_playtime's running TOTALS (it holds each game's total per day) -
     now each day's change (vgplaytime.PLAYED), like the balance. And dev.ps1 / promote.ps1 threw away `docker compose
     build` failures: a lint warning left the OLD web running while the script said it built (dev showed the old
     calendar) - both now stop and say so.
5j. **Supplies: every hobby's kit** (2026-10-21; user: "broad like the wishlist ... hobby filtering then down another
   layer"). The count and value at the top went. api/app/owned.py: GET /api/owned - volleyball / hiking gear you have,
   garden supplies and seeds (Have / Running low), rifles in use and ammo (rounds left), each with its kind and the panel
   that opens it. InventoryView: a hobby row (All hobbies, Models = the supplies, then each hobby with kit; remembered per
   device), then that hobby's own kinds (Models: its categories). All hobbies shows a section per hobby.
5k. **Supplies: tidier, then twelve more** (2026-10-21; user: "too many options and buttons", then from a scan of paintRack,
   Sortly, Grocy and Homebox: "do 1 to 12"). The page keeps search + Add, the hobby row and Options; categories are the
   group headings (no chips), "N need attention" on a hobby's heading filters to those, the rest is under Options.
   88_supplies_more.sql: storage_locations.parent_id (places nest; names unique among siblings; location_path(id) - the
   arrow is chr(8250) so the file stays ASCII: the test database read the literal character wrongly), categories.shelf_months
   (seeded for paint, glue...), supplies.opened_on (set when first opened) / shelf_months / counted_at / swatch /
   reserved_model_id / warranty_until, gear.warranty_until, attachments (receipts, manuals: PDF or photo, 10 MB, removed
   with their item by trigger), todos.supply_id / gear_id (maintenance = a repeating to-do; its next keeps the link).
   supplies.py SUPPLY_SELECT adds location_path, check_by / check_due, reserved_for, warranty_soon and a forecast from the
   stock history (uses_per_month, out_by: 2+ uses in the last year). api/app/supplies_more.py: places (+ move, QR SVG by
   segno - the full SVG: an <img> needs its xmlns), stocktake + count (reason 'counted'), shop list, attachments, bulk
   (move / category / reserve / wishlist / delete), value report (supplies, kits, board games, gear, rifles, ammo, garden).
   Web: components/supplyExtras (colour families, a swatch guessed from the bottle photo in a canvas, the panel's shelf life /
   colour / set aside / forecast / Maintenance / Warranty and receipts - the last two on gear too), InventoryView (row tags,
   colour filter + sort, Select several with a bulk bar, Fill colours from photos, Tools links), core/supplies/SuppliesTools
   (Places and labels, a place's page - where a label's QR leads -, Shopping mode, Stocktake, Value report).
5l. **Wishlist: tidier, then ten more** (2026-10-21; user: "fix up the wishlist tab", then from a look at GiftList, Swym,
   Keepa / CamelCamelCamel, Qapital: "do all 10"). Even spacing, one summary line, quiet placeholders (white only behind a
   real photo), the same card size for every kind, Edit / Details / Remove as small links; a hobby row and Options (group by
   shop or hobby, the bought history, add from a link, the gift list) like Supplies.
   89_wishlist_more.sql: wanted things live in five tables, so wanted_extras / wanted_prices are keyed (kind, ref) - kind
   wish | model | game | gear | garden - with for_model / for_goal, target_price, saved, in_stock + stock_checked, link;
   wanted_history records every buy (the wishlist's own move_to_inventory too). api/app/wanted_more.py: extras (hobby, days
   on the list, below target...), set extras, save, prices, check (Blue Sky gear by its product; Good Games board games by
   handle - asked only when you tap: Good Games is paused in the weekly check), got / ungot (kit In stash, game Owned, gear
   New, garden Have; a supply moves to your supplies), history, from-link + save. refresh_weekly runs after the weekly site
   check (Blue Sky gear only). api/app/linkpeek.py: one product page you pasted (webphoto.check_address: public addresses
   only, every redirect; 2 MB; robots.txt respected; BoardGameGeek and SteamHunters refused) - JSON-LD Product, else Open
   Graph; stand-in in stand_ins.py, refused in conftest. Web: components/wishExtras (ExtraTags, WantedPanel, LinkPanel,
   WishHistory, GiftList at /wishlist/gift), WishlistPage (every card has a tick: bought, with Undo).


5m. **Something on every banner's foot** (2026-10-21; user: "check the banner issues ... with other modules with not having
   the selector"). A script found pages whose picture ended in empty space where the tabs sit: Wishlist on a PC (its
   Supplies / Wishlist tabs are phone-only), Hobbies, and Building my car (SectionTabs hid a hobby with one page). Now:
   SectionTabs shows a one-page hobby's single tab; Hobbies has a "Find a hobby" search (pulled onto the picture by the
   same rule as Journal's and Supplies' search); the Wishlist's hobby row and Options sit on the picture on a PC, frosted
   like the tabs (styles.css, the banner section). Home's banner is left bare on purpose.

5n. **One hobby pick - tried and taken back** (2026-10-21). One hobby pick shared by Goals, Journal, Supplies and the
   Wishlist (and a guessed hobby on each journal page) was built in dev; the user didn't like it and asked for it to be
   reversed the same day, before it was committed. Each page keeps its own filters (Supplies and the Wishlist their own
   hobby rows; Goals by status; Journal by tag and mood). Don't bring it back without asking.
   What the user wanted instead: the Wishlist's hobby row in the banner tabs' style (one frosted bar, the hobby you're
   on a filled pill; styles.css, the banner section) - on the picture on a PC, just under it on a phone.

5o. **Code review, more checks, docs** (2026-10-21; user: "a full code review ... check for bugs, add more tests and
   checks, clean up the documentation"). Found and fixed:
   - Quick add: "weekly until 31 Feb" was a 500 (date(…, 2, 31)); now no end date. A test throws odd words at it.
   - Link reader: BoardGameGeek / SteamHunters were refused only as the pasted link - a shop redirecting there would
     have been read. Now refused at every hop (linkpeek.refused in _get). Odd JSON-LD shapes (offers as strings, an
     ImageObject) were a 500; now skipped / read.
   - Value report left out shooting gear (it named volleyball and hiking only); it now takes db.GEAR_HOBBIES. Add from
     a link could make volleyball or hiking gear only; now shooting too.
   - Wishlist prices kept at the same moment came back in any order (ORDER BY seen_at only): price_id breaks ties,
     for the history and for "the latest price".
   - Shopping mode built its row component inside the page (every row rebuilt on each render); Stocktake swallowed a
     failed save (now says so and stays on the item); a target price saved on every blur (now only when changed).
   - Not a bug: CLAUDE.md said the API runs on UTC - both containers run on Brisbane time (TZ in their Dockerfiles).
     New code still takes "today" from the database.
   New checks: tests/test_web_calls.py (every request() in web/src/api.js is a real route with the right method; 465
   calls, all fine - run_tests.ps1 mounts api.js); ESLint now also fails on plain mistakes (duplicate keys,
   unreachable code, constant conditions...) and React traps (components defined inside components, target=_blank
   without rel, class=) - the code was clean apart from Shopping mode's rows. More tests: the weekly Blue Sky refresh,
   each kind added from a link, undoing a tick, the price de-duplication. pyflakes clean (walkthrough.py's empty
   f-strings and an unused import tidied); pip-audit and npm audit clean; API coverage 91%.
   Docs: README rewritten at the top (the core and all eleven hobbies, sign-in) with its partial API table replaced by
   a module map and /api/docs; "Changing the database" (migrate.ps1) replaces the old "run the SQL yourself"; ROADMAP
   phases brought up to date; CLAUDE.md's stale lines (no login, port 8080, UTC, ~3 minutes, gear hobbies) fixed.

5p. **Health check round 2: backups proven, System panel, lazy hobbies, splits, more tests** (2026-10-21/22; user: "lets
   do it all", Google Drive with 15 GB to work with). Rated 78 before; the security score was mis-marked (security-
   headers.inc already had the CSP, nosniff, framing and referrer headers - the check only looked in nginx.conf).
   - Backups: backup.ps1 reads each backup back (pg_restore --list + the copy's checksum) and once a week restores it
     into a throwaway database (restore_check) comparing every table's row count (a table that changed during the
     backup isn't counted against it). backups\status.json holds each result; Back up now (settings.py) does the same.
     Off-site: prod sends each backup, encrypted with gpg (Git for Windows'; AES-256, the user's password kept by DPAPI
     in %USERPROFILE%\.offtheclock - set with setup-offsite.ps1, never seen by Claude) to a folder Google Drive for
     desktop syncs; scripts\offsite.ps1 keeps 7 days + 4 weeks + 6 months (~200 MB of the 15 GB; a 2 GB budget; videos
     stay on the network drive). restore-offsite.ps1 gets one back. Git's gpg is MSYS: it wants /c/... paths
     (ConvertTo-GpgPath), and 5.1 pipes ASCII unless $OutputEncoding is set (a password with an accent would change).
   - Settings > System (api/app/system.py, components/SystemStatus.jsx): backup, test restore, Drive copy, network copy,
     Steam sync, website check, disk, updates - green / amber / red with what to do; Home shows only what needs a look.
   - check-updates.ps1 (monthly, in dev): PyPI / npm / Docker Hub / Playwright newer versions + pip-audit + npm audit,
     into both copies' backups\updates.json. First run: 20 newer (FastAPI 0.156, React 19.3, BlockNote 0.56, Playwright
     1.64; majors: Mantine 9, Vite 8, React Router 8, ESLint 10), 0 security problems - left for an update round of
     their own. Base images pinned to exact versions (python 3.13.16, node 22.23.3, nginx 1.27.5, postgres 17.11).
   - Permissions-Policy header (passkeys yes; camera, microphone, location, payments, USB no). No HSTS, still on purpose.
   - 90_wanted_cleanup.sql: deleting a kit / game / gear / garden thing / supply wish removes its wishlist extras and
     prices (a trigger per table; the bought history stays).
   - Lazy hobbies: each manifest loads its pages and panels with part() (modules/lazy.js) and keeps only HomeTiles.jsx
     up front; App wraps routes and panels in Suspense. Main download 1.29 MB -> 0.72 MB (350 -> 214 KB compressed),
     Leaflet out of it. web/scripts/check-bundle-size.js fails the build over 260 KB compressed.
   - Splits: styles.css -> web/src/styles/01-25 (cut in order: the built CSS is byte-identical - the same hash; sorting
     rules by area would reorder the cascade, so it wasn't done); garden.py -> + garden_logs.py, garden_today.py (the
     shared log / task SELECTs stay in garden.py: no import circle); walkthrough.py -> wt_common.py + wt_<area>.py, with
     ORDER as names and a check that every @step is in it; HISTORY 1 - 3zzs -> HISTORY-early.md; CLAUDE.md rewritten
     shorter (every rule kept; its handy "pg_dump > backup.sql" was the BOM trap - now backup.ps1).
   - Tests: test_system.py, test_docs.py (CLAUDE.md's db/init and HISTORY ranges, README's module map - it caught the
     map missing system on its first run), every site check with a good and a changed answer (sitecheck 41% -> most),
     the cleanup triggers; web tests (Vitest 5 + jsdom, run_web_tests.ps1, stamped 'web' for promote): formatters,
     colour families, the calendar's helpers, Quick add, Stocktake. Vitest 3 brought tinypool / @vitest/mocker
     advisories (2 critical): Vitest 5 has none and takes Vite 6. The colour-family test found a real bug: supplies with
     no colour sorted between the reds and the oranges (colourKey 999) - now last.
   - The walk-through and the audit answer every request outside the app's own copy themselves (a 1-pixel picture or
     an empty reply: wt_common.offline, ui_audit.offline): Open Library's cover server went down on 2026-10-22 and
     failed the run with book covers the browser was fetching live - the tests never ask outside sites, browsers
     included. Home's System warning button says "Open the System panel" (a "Settings" in it made the walk-through's
     Settings button ambiguous).
   - docs/stack.html: the tech-stack map (published as a page for the user). Its data block names every API module,
     hobby, outside site, tool and script; test_docs fails until anything new is on it.

5q. **Toward 90: updates, more web tests, smaller files** (2026-10-22; user: "how can I make the score better", then
   do 2-4, Google Drive last). Rescored 87 after 5p.
   - Update round (each group tested on its own): FastAPI 0.143 -> 0.156.8 (Starlette 1.9), psycopg-pool 3.3.3,
     BeautifulSoup 4.15.0, pytest 9.1.1; React 19.3.1, BlockNote 0.56.0 (still on Mantine 8 - it takes 8 or 9),
     eslint-plugin-react 7.37.5, Node 22.23.4; Playwright 1.47 -> 1.64 (the noble image; ui_audit finds axe.min.js
     through importlib, not a python3.10 path). All passed first time. Left for later: the majors (Mantine 9, Vite 8,
     React Router 8, ESLint 10, @vitejs/plugin-react 6) and Starlette's "use httpx2 for the test client" warning.
   - Web tests 16 -> 30: the Wishlist (tick, the list catches up after 6 s, undo, a refused tick, the hobby row
     remembered), Goals (sections, the when choices, a new goal opens its page, status chips), a goal's Next up (arrow
     keys reorder and save; a tick says Done with Undo), Supplies (search every word, need attention, a category,
     the hobby row swapping to another hobby's kit). NextUp is exported for its test.
   - Smaller files: InventoryView.jsx 607 -> 414 (+ inventoryParts.jsx), GoalPage.jsx 581 -> 285 (+ goalPageParts.jsx),
     travel.py 589 -> 463 (+ travel_places.py), auth.py 571 -> 427 (+ auth_passkeys.py, included like auth: no blanket
     session check), videogames.py 562 -> 474 (+ videogames_stats.py, included BEFORE videogames - /videogames/stats
     would otherwise be read as /videogames/{app_id}). othergames.py stays whole: its routes use nearly all its sync
     code, so a split would only add an import. The movers report what each part borrows from the other first; the
     things the old file still needs stay there as shared helpers (no import circles).
