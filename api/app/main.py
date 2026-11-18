"""Off the Clock API - the only thing that talks to PostgreSQL.

Core parts every hobby uses, then a module per hobby (docs/ROADMAP.md).

Interactive docs: http://localhost:8000/api/docs

Hobby supplies (shared by every hobby):
    supplies   your inventory, -/+ and stock history     wishlist   things to buy
    products   Tamiya / Hasegawa / Bandai lookups, photos  catalog    Tamiya catalogue search + refresh
    spending   spend + CSV exports
    settings   default shop, price guide, backups          lookups    brands / categories / locations
Core (every hobby):
    todos      the to-do list (under the goals): due days, priority, repeats, a goal or hobby each
    journal    Notion-style pages, tags, @mentions, photos, suggestions, to-dos
    journal_drawings  pen sketches and whiteboard pages (Excalidraw scenes, previews)
    activity   one feed of what you've done (stock, kits, plays, games, journal...)
    auth       signing in: one account, password + authenticator or a passkey, 30-day sessions (every other
               router requires a session)
    banners    the picture at the top of each main page and hobby (yours, or a drawn landscape)
    calendar   events (repeating ones too) and what happened on each day
Hobby modules:
    models     kits (stash), checklists, kit paint lists  build      timer and build log
    colours    colour matches and mixes
    boardgames your games and every play                  volleyball games, gear and videos
               (+ boardgames_people: players, groups, scores, stats, play photos; boardgames_live: a play
               timed and scored as it happens)
    videogames Steam games and achievements (steam.py = the official Steam Web API)
    hiking     hikes from GPX files (AllTrails' export; gpx.py works out the numbers) or logged by hand
    garden     an apartment garden: spaces + layout, containers, plants, care, photos, reminders, today
               (+ garden_guide: the plant guide, what to sow now; garden_items: supplies, seeds, Bunnings links;
               garden_doctor: what's wrong with a plant - signs, causes, what to do)
    shooting   precision shooting: rifles, factory ammo, ranges, licence (+ shooting_sessions: sessions,
               groups, DOPE, the dashboard; shooting_shots: each shot, photos and videos; shotmath: MOA / MIL, velocities)
    travel     trips (ideas, planned, now, past), places (the map, the bucket list), countries, the dashboard
               (+ travel_trip: bookings, the day plan, money, packing, journal and photos; frankfurter: exchange rates)
    vinyl      records (Discogs: discogs.py), the listening log, stats, the insurance export (+ vinyl_sync: the Discogs
               sync, weekly values, Last.fm scrobbling: lastfm.py)
    sudoku     your games (made, graded and explained in the browser: modules/sudoku/engine.js), the daily puzzle, stats
    golf       courses (OpenStreetMap maps: golf_map.py), tees, the bag, practice, settings (+ golf_rounds: rounds played
               live or typed in, shots, the handicap, stats; golf_scores: scoring; golfmath: the sums)
    language   languages, the study log, input hours, resources, the CEFR can-do list, the dashboard (+ language_cards:
               flashcards and reviews, scheduled by FSRS in srs.py; language_course: the built-in courses - lessons,
               progress, the cards a lesson adds; language_sentences: Tatoeba's sentences to read at your
               level, langwords: a sentence's words)
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from . import (activity, auth, auth_passkeys, banners, boardgames, boardgames_live, boardgames_people, bookseries, build, calendar, calendar_feed, catalog, chess, chess_insights, chess_review, chess_trainer, colours, garden, garden_doctor, garden_guide,
               garden_items, garden_logs, garden_today, focus, goals_review, journal_day, travel_extras,
               gear, goals, hiking, journal, journal_drawings, journal_more, calendar_more, owned, supplies_more, wanted_more, shooting, shooting_sessions, shooting_shots, ballistics, travel, travel_places, travel_trip,
               gundam, lookups, minis, vgsync, models, othergames, products, reading, readimport, reading_more, reading_recs, recipes, settings, sitecheck, spending, supplies, vbclips, vbcoach, vbstats, vgfind, vgfriends, videogames, videogames_stats, wanted, webphoto,
               golf, golf_rounds, language, language_cards, language_course, language_sentences, sudoku, system, todos, vinyl, vinyl_care, vinyl_more, vinyl_sync, volleyball, warhammer, wishlist)
from .db import db

# The walk-through's throwaway copy never asks the real outside sites (small shops among them): stand-ins answer.
if os.environ.get("OUTSIDE_SITES") == "stand-ins":
    from . import stand_ins
    stand_ins.install()

@asynccontextmanager
async def lifespan(_app):
    """While the API runs: the daily Steam sync (videogames.py) - only when a key is set - and the
    daily chess.com sync (chess.py; it waits until a username is set). DAILY_SYNCS=off skips both
    (the walk-through's throwaway copy must not sync on its own)."""
    vbclips.forget_unfinished()            # a highlight video being made when the app stopped
    language_course.courses()              # the language courses, read and checked once (a bad unit: a warning)
    if os.environ.get("DAILY_SYNCS", "on") != "off":
        if os.environ.get("STEAM_API_KEY"):
            vgsync.start_daily_sync()
        chess.start_daily_sync()
        if os.environ.get("DISCOGS_TOKEN"):
            vinyl_sync.start_weekly()      # records' values, a week apart
        sitecheck.start_weekly()          # the websites the app reads, once a week
    yield


app = FastAPI(title="Off the Clock API", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

for part in (activity, banners, goals_review, goals, todos, focus, journal_drawings, journal_more, journal_day, journal, calendar_feed, calendar, calendar_more, owned, supplies_more, supplies, wanted_more, wishlist, products, catalog, models, minis, build, recipes, colours,
             boardgames_people, boardgames_live, boardgames, volleyball, gear, vbclips, vbcoach, vbstats, othergames, vgfind, vgfriends, videogames_stats, videogames, chess_trainer, chess_insights, chess_review, chess, reading, reading_more, readimport, hiking, garden, garden_logs, garden_today, garden_doctor, garden_guide, garden_items, shooting, shooting_sessions, shooting_shots, ballistics, travel, travel_places, travel_extras, travel_trip, vinyl_sync, vinyl, vinyl_care, vinyl_more, sudoku, golf, golf_rounds, language, language_cards, language_course, language_sentences, reading_recs, bookseries, warhammer, gundam, spending, settings, system, sitecheck, lookups, webphoto, wanted):
    app.include_router(part.router, dependencies=[Depends(auth.require_session)])   # signed in only (auth.py)
app.include_router(auth.router)                  # signing in itself: each route checks what it needs
app.include_router(auth_passkeys.router)         # (passkeys: the same - split out of auth.py)
app.include_router(calendar_feed.public)         # the phone calendar's feed: its own secret key instead of a sign-in


@app.get("/api/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/about")
def about():
    """Which copy of the app this is: "prod" (your real data) or "dev" (a test copy)."""
    return {"env": os.environ.get("APP_ENV", "prod")}
