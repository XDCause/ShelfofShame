"""Wikidata (https://www.wikidata.org): the free, open database behind Wikipedia. No key, no
account. Used to find a board game by name and fill in the publisher's facts.

    search(name)   board games whose name matches, best match first: Wikidata's own name search
                   (EntitySearch) inside one SPARQL query, kept to items that are board / card
                   games or have a BoardGameGeek id (a plain search also finds cities, video games...)
    game(qid)      one game, the same shape
    photo(game)    the game's picture from Wikimedia Commons (600 px wide), checked like any
                   downloaded photo (images.fetched_photo)

A game: wikidata_id, name, description, year (earliest), min_players / max_players (widest - some
games list several editions), play_minutes, min_age, designer, publisher, bgg_id, image (a Commons
file page URL). BGG's ratings, ranks and complexity aren't on Wikidata.

Wikimedia asks for a User-Agent that says who's asking, with a way to get in touch.
"""
import re
import urllib.parse

import httpx

from .images import fetched_photo

SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "OffTheClock/1.0 (personal hobby tracker; https://github.com/XDCause/ShelfofShame)",
           "Accept": "application/sparql-results+json"}
TIMEOUT = 30
MINUTE, HOUR = "Q7727", "Q25235"
GAME_KINDS = "wd:Q131436 wd:Q142714 wd:Q1272194"      # board game, card game, tabletop game


class WikidataError(Exception):
    """A message for the user: Wikidata unreachable or busy."""


def _query(q: str) -> list[dict]:
    try:
        r = httpx.post(SPARQL, data={"query": q, "format": "json"}, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise WikidataError(f"Couldn't reach Wikidata ({e.__class__.__name__}).") from None
    if r.status_code == 429:
        raise WikidataError("Wikidata says it's busy. Try again in a minute.")
    if r.status_code != 200:
        raise WikidataError(f"Wikidata didn't answer (HTTP {r.status_code}).")
    return [{k: v["value"] for k, v in row.items()} for row in r.json()["results"]["bindings"]]


# Everything about the games in ?g, one row per value (GROUP BY collapses them in _games()).
FACTS = """
  OPTIONAL { ?g wdt:P2339 ?bgg }
  OPTIONAL { ?g wdt:P1872 ?min }
  OPTIONAL { ?g wdt:P1873 ?max }
  OPTIONAL { ?g p:P2047/psv:P2047 [wikibase:quantityAmount ?time; wikibase:quantityUnit ?unit] }
  OPTIONAL { ?g wdt:P577 ?date }
  OPTIONAL { ?g wdt:P2899 ?age }
  OPTIONAL { ?g wdt:P18 ?image }
  OPTIONAL { ?g wdt:P50|wdt:P178|wdt:P287 ?d . ?d rdfs:label ?designer FILTER(lang(?designer) = "en") }
  OPTIONAL { ?g wdt:P123 ?p . ?p rdfs:label ?publisher FILTER(lang(?publisher) = "en") }
  OPTIONAL { ?g schema:description ?description FILTER(lang(?description) = "en") }
  ?g rdfs:label ?name FILTER(lang(?name) = "en")
"""


def _games(rows: list[dict]) -> list[dict]:
    games: dict[str, dict] = {}
    for r in rows:
        qid = r["g"].rsplit("/", 1)[-1]
        g = games.setdefault(qid, {"wikidata_id": qid, "name": r["name"], "description": r.get("description"),
                                   "order": int(r.get("ordinal", 0)), "years": set(), "mins": set(), "maxes": set(),
                                   "times": set(), "ages": set(), "designers": [], "publishers": [], "bgg": set(),
                                   "images": []})
        for key, field in (("year", "years"), ("min", "mins"), ("max", "maxes"), ("age", "ages"), ("bgg", "bgg")):
            value = r.get("date" if key == "year" else key)
            if value and re.fullmatch(r"-?\d+(\.\d+)?|\d{4}-.*", value):
                g[field].add(int(value[:4]) if key == "year" else int(float(value)))
        if r.get("time") and r.get("unit"):
            unit = r["unit"].rsplit("/", 1)[-1]
            if unit in (MINUTE, HOUR):
                g["times"].add(round(float(r["time"]) * (60 if unit == HOUR else 1)))
        for key, field in (("designer", "designers"), ("publisher", "publishers"), ("image", "images")):
            if r.get(key) and r[key] not in g[field]:
                g[field].append(r[key])
    out = []
    for g in sorted(games.values(), key=lambda g: g["order"]):
        mins, maxes = {m for m in g["mins"] if m > 0}, {m for m in g["maxes"] if m > 0}
        out.append({
            "wikidata_id": g["wikidata_id"], "name": g["name"], "description": g["description"],
            "year": min(g["years"]) if g["years"] else None,
            "min_players": min(mins) if mins else None, "max_players": max(maxes) if maxes else None,
            "play_minutes": max(g["times"]) if g["times"] else None,
            "min_age": min(g["ages"]) if g["ages"] else None,
            "designer": ", ".join(g["designers"][:3]) or None, "publisher": ", ".join(g["publishers"][:2]) or None,
            "bgg_id": min(g["bgg"]) if g["bgg"] else None,
            "image": g["images"][0] if g["images"] else None,
            "image_url": thumb(g["images"][0], 300) if g["images"] else None,
        })
    return out


def thumb(file_page: str, width: int) -> str:
    """A Commons file ("…/Special:FilePath/Catan.jpg") at a width: Commons makes the size itself."""
    name = urllib.parse.unquote(file_page.rsplit("/", 1)[-1])
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(name)}?width={width}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def search(name: str, limit: int = 8) -> list[dict]:
    rows = _query(f"""
SELECT * WHERE {{
  SERVICE wikibase:mwapi {{ bd:serviceParam wikibase:endpoint "www.wikidata.org"; wikibase:api "EntitySearch";
      mwapi:search "{_escape(name)}"; mwapi:language "en"; mwapi:limit "30".
      ?g wikibase:apiOutputItem mwapi:item. ?ordinal wikibase:apiOrdinal true. }}
  FILTER(EXISTS {{ ?g wdt:P2339 [] }} || EXISTS {{ VALUES ?kind {{ {GAME_KINDS} }} ?g wdt:P31/wdt:P279* ?kind }})
  {FACTS}
}}""")
    # Leave out items with nothing but a name (a "Catan series", an episode): nothing to fill in.
    useful = [g for g in _games(rows) if g["bgg_id"] or g["year"] or g["min_players"] or g["image"]]
    return useful[:limit]


def game(qid: str) -> dict | None:
    if not re.fullmatch(r"Q\d+", qid):
        return None
    found = _games(_query(f"SELECT * WHERE {{ VALUES ?g {{ wd:{qid} }} {FACTS} }}"))
    return next((g for g in found if g["wikidata_id"] == qid), None)


def photo(found: dict) -> tuple[bytes | None, str | None]:
    """The game's Commons picture, 600 px wide (None, None if it has none or it isn't an image)."""
    if not found.get("image"):
        return None, None
    try:
        r = httpx.get(thumb(found["image"], 600), headers={"User-Agent": HEADERS["User-Agent"]}, timeout=TIMEOUT,
                      follow_redirects=True)
    except httpx.HTTPError:
        return None, None
    return fetched_photo(r)
