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
"""
import os

from fastapi import FastAPI

from . import (activity, boardgames, build, calendar, catalog, colours, journal, journal_drawings, lookups, models,
               products, settings, spending, supplies, volleyball, wishlist)
from .db import db

app = FastAPI(title="Off the Clock API", docs_url="/api/docs", openapi_url="/api/openapi.json")

for part in (activity, journal_drawings, journal, calendar, supplies, wishlist, products, catalog, models, build, colours,
             boardgames, volleyball, spending, settings, lookups):
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
