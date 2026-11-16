# Market review (2026-11-16)

What the leading apps for each hobby offer that Off the Clock doesn't (yet), ranked by value for the effort, and
what Off the Clock already does better. Researched from app listings, help pages and reviews (developers' own claims
in places), checked against this code. Effort: S = an evening, M = a day or two, L = a bigger project.
Rules kept: no scraping of sites that forbid it (BoardGameGeek, SteamHunters, HowLongToBeat, Scalemates), official
APIs with personal keys only, nothing social.

**Status:** items marked DONE are built (HISTORY 5y and 5z). Left on purpose: anything needing a new outside service or account (RetroAchievements, an "am I back?" alert service, plant ID by photo, email-in / booking emails) and the big ones (offline map navigation, killer / thermo / arrow sudoku).

## Across the app (the best picks)
| Pick | Area | Effort | Why |
|---|---|---|---|
| **DONE** Calendar feed (.ics) for your phone's calendar | Core | S | TripIt, Fantastical, TickTick all have it; trips, events and bookings on your phone's own calendar |
| "Am I back?" safety check for hikes | Hiking | M | AllTrails Lifeline: alert someone if you're not back by a time - useful for Patagonia |
| **DONE** Ballistic solver + density altitude | Shooting | M | Strelok / Hornady 4DOF: predicted drop and drift to cross-check your DOPE |
| **DONE** Trip cost splitting | Travel | M | Wanderlog / Splitwise |
| **DONE** Paint recipes per mini / model | Models | M | BrushLog, Paintledger |
| **DONE** Weather-aware garden care schedule | Garden | M | Planta |
| **DONE** Chess clock / time-trouble stats | Chess | S-M | Aimchess (chess.com PGNs carry the clock) |
| **DONE** Board game H-index, streaks, first-player stats | Board games | S | BG Stats |
| **DONE** Video game backlog status + "what next" | Video games | S-M | Backloggd, HowLongToBeat |
| **DONE** Vinyl "play something" (least played, never played) | Vinyl | S | |

## Scale models, Warhammer, Gundam
1. **DONE** Paint recipes attached to a mini, unit or kit (steps + paints) - [BrushLog](https://apps.apple.com/be/app/brushlog/id6763442950), [Paintledger](https://apps.apple.com/be/app/paintledger/id6762442016). M.
2. **DONE** "Can I paint this now?" - for a kit's paint list: owned / low / missing, one tap to the shopping list - BrushLog, [Hobby Codex](https://apps.apple.com/lu/app/id6769028242). S-M.
3. Progress photos with paints pinned on them - [Miniature Painting Companion](https://f-droid.org/en/packages/com.cdevaux.miniature_painting_companion/). M.
4. **DONE** Stage pipeline with time per stage and "painted this year" tally. S.
5. **DONE** Closest paint you own in another brand when one runs out - [paintRack](https://apps.apple.com/us/app/paintrack/id1490523130). S-M.
6. **DONE** CSV export of stash, paints and builds. S.
Better already: kits, Warhammer and Gundam in one app with real timers and the calendar; the market is single-purpose apps with free-tier caps.

## Supplies and wishlist
1. **DONE** Low-stock report and opened-on / expiry dates for paints, glue, putty - [Sortly](https://www.sortly.com/solutions/home-inventory-software). S.
2. **DONE** Price history chart and a price-drop flag on wishlist items (official shop feeds only). S-M.
3. **DONE** Paint-rack view: a swatch grid by brand and number - paintRack. M.
4. Stocktake by scanning a place's QR label then each barcode. M.
Better already: nested places with QR labels, real shop catalogues, no per-item pricing.

## Board games
1. **DONE** H-index, win streaks, first-player win rate, stats per player combination - [BG Stats](https://apps.apple.com/us/app/id892542000). S-M.
2. **DONE** Per-player turn timers in live play (chess-clock style) - [Clepsydris](https://apps.apple.com/us/app/clepsydris-board-game-app/id1475417618). M.
3. **DONE** Score by round (a round x player grid) and per-category score stats - [Board Record](https://apps.apple.com/us/app/board-record/id1598527865). M.
4. **DONE** Tags on a play ("won on the last turn", "first time with the expansion"). S.
5. **DONE** Unplayed shelf / not played in a year nudge. S.
Better already: live play with stages, photos and teach notes in the same app as the collection, journal and calendar; free.

## Video games
1. **DONE** Backlog status (backlog / playing / finished / dropped) and a "what next" pick - Backloggd, HowLongToBeat. S-M.
2. **DONE** Time to beat: your own estimate field, or the median of your finished games (HLTB has no API - don't scrape). S.
3. **DONE** Next easiest achievement from the rarity you already have. S.
4. **DONE** Cost per hour played. S.
5. RetroAchievements (free personal API key). M.
Better already: Steam, Epic, Ubisoft, rarity, recap and goals together with no tracker account.

## Chess
1. **DONE** Clock stats: time per move vs the eval swing, time-trouble blunders, when you flag - [Aimchess](https://aimchess.com). S-M.
2. **DONE** Your own blunders as a puzzle set with spaced repetition (the trainer's scheduler). M.
3. **DONE** "Lost a won position" replays from the review's swings. S-M.
4. **DONE** Skill scores (tactics, endgames, converting an advantage, resourcefulness) from your reviews. M.
5. **DONE** Endgame-type breakdown (rook, pawn, minor-piece endgames). M.
Better already: local Stockfish at no cost (Aimchess charges for deep reports); openings, review and trainer in one place.

## Sudoku
1. **DONE** Per-technique stats (hints asked most, slowest techniques) feeding practice - Good Sudoku. S-M.
2. **DONE** Paste a puzzle as an 81-character string. S (check: typed entry exists).
3. **DONE** Solving path stepper for a whole puzzle. M.
4. **DONE** Colour / chain marking tools. M.
5. Killer / thermo / arrow variants. L.
Better already: technique grading, the Hardest 100, events, replay, X-sudoku, no ads or leaderboard.

## Reading
1. **DONE** Pace forecast: pages a day, the finish date, on track for the year's goal. S.
2. **DONE** Re-reads (more than one read-through of a book). S-M.
3. **DONE** Year in review card; stats by length and format. S-M.
4. **DONE** Private content-warning tags; custom challenges (a book per country). S / M.
Better already: Goodreads import, series, quotes and suggestions privately, no subscription.

## Vinyl
1. **DONE** "Play something": least played / never played / by genre. S.
2. **DONE** Collection value over time from Discogs prices. M (check what's stored).
3. **DONE** Loaned to; cleaning and stylus-hours log. S.
4. **DONE** Insurance export (CSV with values and photos). S.
5. **DONE** Listening year in review with Last.fm. S-M.
Better already: Discogs sync, plays, Last.fm and the crate together; CLZ is a subscription.

## Volleyball
1. **DONE** Serve / pass ratings on the 0-3 scale. S.
2. **DONE** Rotation stats (side-out % by rotation) - [Balltime](https://academy.balltime.com/stats/attack-tendencies-and-rotation-charts), [Hudl](https://hudl.com/products/assist/volleyball/ai). M.
3. **DONE** Clips tagged by skill and outcome, opened from a stat. M.
4. **DONE** Personal bests and weekly volume per drill. S-M.
Better already: private coach notes, training and gear beside the games; Hudl and Balltime are club products.

## Hiking
1. "Am I back?" check: expected return time, an alert to a contact if late (needs a free push service such as ntfy). M.
2. **DONE** Time estimate for a planned route from your own pace (Naismith / Tobler). S.
3. **DONE** Splits, steepest section, best time on a repeated trail - Strava. S-M.
4. **DONE** Year in review with a heatmap of every track. S-M.
5. Planned-route navigation offline. L.
Better already: photos placed on the track by their time, OpenStreetMap landmarks, gear per hike, no subscription.

## Gardening
1. **DONE** Care schedule per plant that follows the weather (skip watering after rain) - [Planta](https://gardencentermag.com/news/how-this-swedish-plant-care-app-planta-can-help-plant-parents-at-any-stage). M.
2. **DONE** Photo timeline per plant (before / after). S-M.
3. **DONE** Brisbane sowing calendar on the main calendar. M.
4. **DONE** Cost vs harvest per crop. S.
5. **DONE** Manual sun hours per balcony spot on the layout. M.
Better already: the Doctor, the Guide, the balcony layout and Bunnings links.

## Precision shooting
1. **DONE** Ballistic solver (G1 / G7, your BC and velocity) to cross-check DOPE - [Strelok Pro](https://strelok.pages.dev/faq.html). M-L.
2. **DONE** Density altitude per session from the day's weather. M.
3. **DONE** Ammo lot comparison (group size, SD / ES per lot). S.
4. **DONE** Powder temperature sensitivity from your chronograph sessions. S-M.
5. **DONE** Printable DOPE / range card. S (check what prints now).
Better already: sessions, rifles, ammo stock, gear and the live board together, with group maths.

## Travel
1. **DONE** Calendar feed (.ics) of trips and bookings. S.
2. **DONE** Shared costs: who paid, who owes, in any currency. M.
3. Paste a booking confirmation to add it (parsed locally, no email access). M-L.
4. **DONE** Day-by-day map with travel times between stops. M.
Better already: memories, reusable packing lists, budget and currency, offline copy with no subscription.

## Journal, goals, calendar, Home
1. **DONE** .ics calendar feed out (and later, subscribe to another calendar). S / M.
2. **DONE** Focus timer on a to-do or goal, logged against it - TickTick. S-M.
3. **DONE** Voice dictation in the journal (the browser's speech recognition). S.
4. **DONE** A day's entry that gathers its events, hikes, sessions and photos - [Day One](https://dayoneapp.com/features/). M.
5. **DONE** Streak freezes and a weekly review for habits - Streaks, Habitica. S.
Better already: one linked database across the journal, goals, calendar and every hobby; passkeys and encrypted off-site backups; no subscription.
