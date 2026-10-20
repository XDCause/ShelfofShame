# Off the Clock - design system

The look is **moody botanical editorial**: a personal space that feels like an editorial magazine, a journal and a
curated collection, with the usefulness of a good app. It was rebuilt 2026-10-20 (HISTORY 4w). This file is the
"why" behind `web/src/styles.css`; read it before adding a page or a component.

## Principles (from the research, applied)

| Principle | Where it comes from | What it means here |
|---|---|---|
| Show where you are | NN/g heuristic 1 (system status), 6 (recognition over recall) | Every main page opens with a banner naming it; the sidebar marks the page; the nav bar shows the name once the banner scrolls away; a hobby's tabs show the page you're on as a filled pill. |
| One strong action per screen | Refactoring UI hierarchy; NN/g 8 (minimalist) | `.primary` (a parchment pill on dark, pine on light) is used once per area: Write today's entry, + Add a book... Everything else is `.secondary` or `.plain`. |
| Hierarchy through size and weight, not colour | Refactoring UI | Playfair Display for page titles, card titles and big numbers; Inter for everything you read and operate; muted text for metadata. Colour is for meaning (status, the tint) and identity (a hobby's hue). |
| Colour never alone | WCAG 1.4.1 | Status pills always carry a word; hobby colours always sit beside the hobby's name and icon. |
| Atmosphere without noise | the brief | Atmosphere comes from the banners (your photo or a drawn landscape) and type - not from glows, blobs or glass. Cards are flat with thin borders and small radii. |
| Consistent and conventional | NN/g 4, Jakob's law | One button family, one pill, one card, one panel (a side sheet on a computer, a bottom sheet on a phone), one set of tabs. |
| Forgiving | NN/g 3, 5, 9 | Undo bars, confirmations for deletes (unchanged), errors in plain words; the banner picture can always go back to the drawing. |
| Fast enough to feel direct | Doherty threshold (~400 ms) | Motion is short: 140 ms for hovers, 240-400 ms for page and panel entrances, transform/opacity only. |
| Accessible | WCAG 2.2 AA | Text >= 4.5:1 (checked for every token in both themes), focus ring 2 px in the tint (>= 3:1), targets >= 24 px (44 px on phones), reflow to 320 px without sideways scrolling (the walk-through checks every page at 390 px), reduced motion turns movement off. |
| Use real content | the brief | Pictures are your own (banners, kit and book photos); the drawn landscapes are a fallback, never stock images. Nothing on screen is mock data. |

## Tokens (`:root` in styles.css; dark mode swaps the values)

- **Surfaces**: `--bg`, `--surface` (cards), `--elevated` (menus, sheets), `--field`, `--border`, `--separator`, `--fill`, `--fill-2`.
- **Text**: `--text`, `--muted`, `--faint`.
- **Interaction**: `--tint` (anything tappable: links, icons, focus), `--tint-soft`, `--primary-bg` / `--primary-text`
  (the one strong button), `--on-tint`, `--on-solid` (text on a solid status colour).
- **Status**: `--ok`, `--low`, `--out` (+ `-bg`); kinds of things: `--purple`, `--teal`; warmth: `--ember`.
- **Sidebar**: `--side-bg`, `--side-text`, `--side-muted`, `--side-active` - deep pine in both themes.
- **Area colour**: `--hue` - set inline from a hobby's manifest (`hue`) or `core/areas.js`; `--hue-ink` mixes it
  with the text colour so it reads in both themes.
- **Type**: `--font-display` (Playfair Display), `--font-ui` (Inter), `--font-script` (Caveat - Home's one
  handwritten line only); sizes `--text-xs` ... `--text-4xl`.
- **Space**: `--space-1` (4 px) ... `--space-7` (48 px). **Shape**: `--radius` (12 px), `--radius-sm` (8 px), pills 999 px.
- **Motion**: `--fast`, `--medium`, `--slow`, `--ease-out`. **Elevation**: `--card-shadow` (barely there),
  `--lift-shadow` (hover), `--shadow` (menus, panels).

Palette: near-black pine `#111915`, pine `#17211b`, forest `#3d6a2c`, sage `#abc99a`, parchment `#ece3cf` / `#efe8d8`,
terracotta `#b5552f` / `#d9825a`, ochre `#94570c` / `#e5b562`, rust `#a93b26` / `#e8846c`, dusty blue `#2b6680` / `#8dbbd2`.

## Components and patterns

- **Shell** (App.jsx, core/Navigation.jsx): pine sidebar (core pages, hobbies with their colours, a daily nudge,
  Settings); a nav bar with search, scan and (phones) settings that floats clear over the banner and turns solid
  on scroll; phones get a bottom tab bar instead of the sidebar.
- **Banner** (components/PageBanner.jsx, Home's `HomeHero`): every top-level page and hobby. Picture = your photo
  (`banners` table, "Picture" menu: choose, nudge up/down, back to the drawing) or `Landscape.jsx` (peaks, hills,
  forest, coast, night - seeded, in the area's hue). Darkened left for the words, faded into the page at the foot.
- **Tabs**: `.section-tabs` - words, the current page a filled pill, a hairline under the row; scroll sideways on phones.
- **Cards**: `.card` (surface, 1 px border, 12 px radius). Picture cards (`.glance-card`, `.next-adventure`,
  `.model-card`) put the image first and the words over or under it.
- **Lists**: `.list` / `.plain-list` rows with hairlines; tables in `.table-wrap` for dense data (supplies).
- **Buttons**: `.primary` (one per area), `.secondary` (tinted), `.plain` (text), `.icon-btn`, `.chip-filter` (filters;
  pressed = the primary colours), `.segmented` (a small choice).
- **Panels**: `Drawer` - right side sheet on a computer, bottom sheet on a phone.
- **Journal**: a notes page is warm paper in both themes (dark ink, its own quiet colours; the editor is always
  light); whiteboards stay full width on the page colour.

## Route inventory (2026-10-20)

Core: Home `/`, Goals `/goals` (+ a goal), Journal `/journal` (+ a page), Calendar `/calendar`, Supplies `/supplies`,
Wishlist `/wishlist`, Hobbies `/hobbies`. Hobbies (pages): Models (Kits, Warhammer, Gundam, Colours), Board games
(Games, Plays), Volleyball (Games, Videos, Coach, Gear), Video games (Dashboard, Games, Stats, Friends), Chess
(Dashboard, Games, Openings), Reading (Dashboard, Books, For you, Stats, Quotes), Building my car (The build - dev
only), Travel (Dashboard, Trips, Places, Packing lists), Precision shooting (Dashboard, Sessions, Rifles, Ammo, DOPE,
Gear), Hiking (Dashboard, Hikes, Gear), Gardening (Today, Layout, Plants, Guide, Doctor, Harvests, Supplies). About 30
panels (items, kits, games, books, trips, sessions...) open over any page. Every one is covered by the walk-through.

## Adding something

- A new hobby: give its manifest a `hue` (a mid-tone, related to the palette) and a `banner` ({scene, seed, tagline}).
- A new class: a name nobody else uses (the build fails on a clash); colours from tokens only.
- A new picture: give it a fixed aspect ratio (no layout shift) and `loading="lazy"` below the fold.
