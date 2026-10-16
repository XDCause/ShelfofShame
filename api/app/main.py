"""Off the Clock API - the only thing that talks to PostgreSQL.

Core parts every hobby uses, then a module per hobby (docs/ROADMAP.md).

Interactive docs: http://localhost:8000/api/docs

Hobby supplies (shared by every hobby):
    supplies   your inventory, -/+ and stock history     wishlist   things to buy
    products   Tamiya / Hasegawa / Bandai lookups, photos  catalog    Tamiya catalogue search + refresh
    spending   spend + CSV exports
    settings   default shop, price guide, backups          lookups    brands / categories / locations
Core (every hobby):
    journal    Notion-style pages, tags, @mentions, photos, suggestions, to-dos
    journal_drawings  pen sketches and whiteboard pages (Excalidraw scenes, previews)
    activity   one feed of what you've done (stock, kits, plays, games, journal...)
    calendar   events (repeating ones too) and what happened on each day
Hobby modules:
    models     kits (stash), checklists, kit paint lists  build      timer and build log
    colours    colour matches and mixes
    boardgames your games and every play                  volleyball games, gear and videos
    videogames Steam games and achievements (steam.py = the official Steam Web API)
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import (activity, boardgames, bookseries, build, calendar, catalog, chess, colours, gear, goals, journal, journal_drawings,
               gundam, lookups, minis, vgsync, models, othergames, products, reading, readimport, reading_recs, settings, sitecheck, spending, supplies, vbclips, vbcoach, vgfind, vgfriends, videogames, wanted, webphoto,
               volleyball, warhammer, wishlist)
from .db import db

@asynccontextmanager
async def lifespan(_app):
    """While the API runs: the daily Steam sync (videogames.py) - only when a key is set - and the
    daily chess.com sync (chess.py; it waits until a username is set). DAILY_SYNCS=off skips both
    (the walk-through's throwaway copy must not sync on its own)."""
    vbclips.forget_unfinished()            # a highlight video being made when the app stopped
    if os.environ.get("DAILY_SYNCS", "on") != "off":
        if os.environ.get("STEAM_API_KEY"):
            vgsync.start_daily_sync()
        chess.start_daily_sync()
        sitecheck.start_weekly()          # the websites the app reads, once a week
    yield


app = FastAPI(title="Off the Clock API", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

for part in (activity, goals, journal_drawings, journal, calendar, supplies, wishlist, products, catalog, models, minis, build, colours,
             boardgames, volleyball, gear, vbclips, vbcoach, othergames, vgfind, vgfriends, videogames, chess, reading, readimport, reading_recs, bookseries, warhammer, gundam, spending, settings, sitecheck, lookups, webphoto, wanted):
    app.include_router(part.router)


@app.get("/api/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/about")
def about():
    """Which copy of the app this is: "prod" (your real data) or "dev" (a test copy)."""
    return {"env": os.environ.get("APP_ENV", "prod")}
