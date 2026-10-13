# Roadmap: from model-kit inventory to a hobby hub

Agreed 2026-10-13. Shelf of Shame grows into **one app with a shared core and a module per
hobby**, rather than one app per hobby: "a bit like TechOne as an ECM, with different modules
and parts".

## Decisions so far

| Question | Decision |
|---|---|
| Journal editor | **Notion-style blocks** (type `/` for headings, to-dos, photos, quotes; drag blocks; `@` mentions). Planned library: BlockNote (open source, built on TipTap/ProseMirror). |
| App name | **Off the Clock** (chosen 2026-10-13). "Shelf of Shame" is the model-kit module's name. Internal names (containers, database, volume) stay as they are. |
| First new modules | **Board games** and **Volleyball**, after the journal and calendar. Scuba diving, woodworking and pottery come later. |
| Environments | **Dev and prod on this PC.** Done: see README "Dev and prod". |

## The shape of the app

```
Core (every module uses it)
  Home        today: what's on, running timer, recent entries, things running low
  Journal     Notion-style pages; @mention anything (a model, a game, a match); tags
  Calendar    month / week / list; planned things + what happened, coloured per module
  Shared      search, tags, photos/attachments, timers, settings, backups, exports

Modules (one per hobby, switched on in Settings)
  Model kits      (today's app: inventory, wishlist, models, colours)
  Board games     collection + plays
  Volleyball      games and training
  Scuba, Woodworking, Pottery ... later
```

### The building blocks every module is made of

Most hobbies are combinations of the same few things, so modules share the core's tables and
screens and only add their own fields:

| Block | What it is | Model kits | Board games | Volleyball | Scuba | Woodworking / pottery |
|---|---|---|---|---|---|---|
| **Collection** | things you own or want | kits | games | – | certifications, gear | – |
| **Project** | something you make, in steps | builds | – | – | – | pieces |
| **Session** | time spent on a date (shows on the calendar) | build sessions | plays | games, training | dives | shop time, firings |
| **Log / journal** | notes and photos | build log | play notes | match notes | dive notes | progress photos |
| **Supplies** | consumables with stock levels | paints, glue | – | – | – | timber, clay, glazes |

Plan for the database:
- **Core tables:** `journal_pages`, `calendar_events` (planned things), `tags`, `attachments`, and
  `links` (anything mentions anything).
- **Module tables** with a prefix: `bg_games`, `bg_plays`, `vb_matches`... Each module's fields
  stay real columns (checked and queryable), not loose JSON.
- **The calendar reads every module's dated rows through one view** (`v_calendar`), so a new
  module appears on it by adding to the view.

Plan for the code:
- `api/app/modules/<name>/` (routes, SQL, tests) and `web/src/modules/<name>/` (pages,
  panels).
- **A module manifest** (name, icon, colour, pages, calendar sources, Home widgets) is the only
  thing the core needs to know, so adding a hobby means adding a folder.

### The new UI

- **Desktop:** a sidebar with Home, Journal, Calendar, then each switched-on hobby (which
  expands to its pages), Settings at the bottom.
- **Phone:** a tab bar with Home, Journal, Calendar, Hobbies and More.
- **Real page addresses** (React Router), so back, refresh, bookmarks and links into a journal
  page all work.
- **Same Apple-style look:** system font, grouped lists, sheets on phones, dark mode.

## Phases

Each phase is built and tested in the dev copy, then promoted (`promote.ps1`).

| # | Phase | Notes |
|---|---|---|
| 0 | **Dev and prod** | DONE 2026-10-13: worktree, dev.ps1, promote.ps1, migrate.ps1, DEV badge |
| 1 | **New UI shell** | DONE 2026-10-13 (in dev): React Router, sidebar / tab bar, Home page, module manifest (web/src/modules). Model kits moved in unchanged. |
| 2 | **Journal** | DONE 2026-10-13 (in dev): pages, BlockNote editor, photos, tags, @mentions of models / supplies / pages, search, "In the journal" on panels |
| 2b | **Journal actions + to-dos** | DONE 2026-10-13 (in dev): suggestions from what a page says ("bought ... started @Sherman" -> In progress), to-dos from check lists, margin fixes |
| 2c | **A more creative look** | DONE 2026-10-13 (in dev), from two reference designs: navy dark theme + theme switch, hero, stat tiles, activity feed, quick actions, running low, top-bar search, journal cards; journal "Add to wishlist" suggestions |
| 3 | **Calendar** | Month / week / list views; planned events; past activity from every module |
| 4 | **Board games** | Collection (with an unplayed "shelf of shame"), plays (players, scores, winner) |
| 5 | **Volleyball** | Games and training: team, opponent, result, sets, your stats, notes |
| 6+ | Scuba, woodworking, pottery... | One module at a time |

## Before going public

Every new data source or shortcut gets a row in [BEFORE_GOING_PUBLIC.md](../BEFORE_GOING_PUBLIC.md),
for example board game data from BoardGameGeek, whose API has its own terms.
