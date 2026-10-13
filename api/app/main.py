"""Shelf of Shame API - the only thing that talks to PostgreSQL.

Interactive docs: http://localhost:8000/api/docs

Each part of the app is its own module with its own routes:
    supplies   your inventory, -/+ and stock history     wishlist   things to buy
    products   Tamiya / Hasegawa lookups, barcodes, photos catalog    Shop Tamiya search + refresh
    models     kits (stash), checklists, kit paint lists  build      timer and build log
    colours    colour matches and mixes                    spending   spend + CSV exports
    settings   default shop, price guide, backups          lookups    brands / categories / locations
"""
import os

from fastapi import FastAPI

from . import (build, catalog, colours, lookups, models, products, settings, spending, supplies,
               wishlist)
from .db import db

app = FastAPI(title="Shelf of Shame API", docs_url="/api/docs", openapi_url="/api/openapi.json")

for part in (supplies, wishlist, products, catalog, models, build, colours, spending, settings, lookups):
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
