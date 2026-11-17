"""The weekly check of the websites the app reads. The tests use saved copies of each site's pages,
so when a site changes its layout the tests still pass and only the real look-up breaks; this does one
real, polite look-up per site and checks the answer still has the shape the app expects.

    GET  /site-checks        every site's last result: {sites, running, failing, last_run}
    POST /site-checks/run    check them all now (in the background; poll GET)

Runs by itself once a week (start_weekly(), from main.py unless DAILY_SYNCS=off). Each site is asked
once per check, through the same module the app uses (so the same pauses and User-Agent apply). This is the
only automatic live contact with outside sites: the tests and the walk-through use stand-ins (stand_ins.py);
"Check now" in Settings looks again when something seems wrong.
"""
import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks

from . import (bluesky, bunnings, exophase, frankfurter, gameology, goodgames, hasegawa, hlj, lichess, stedi, trumpeter, openlibrary, openmeteo, overpass, steam,
               steamhunters, tamiya, wikimedia)
from .db import db

log = logging.getLogger("sitecheck")
router = APIRouter(prefix="/api", tags=["settings"])
WEEKLY = timedelta(days=7)
RETRY = timedelta(days=1)       # a site that failed is asked again (on its own) a day later


class Unexpected(Exception):
    """The site answered, but not with what the app reads."""


def expect(condition, what: str):
    if not condition:
        raise Unexpected(what)


def _tamiya():
    p = tamiya.fetch("81701")
    title = p.get("title") or ""
    expect("XF-1" in title.upper().replace(" ", ""), f"Tamiya's page for 81701 has no XF-1 title ({title!r})")
    expect(p.get("image"), "Tamiya's page has no photo")
    return f"{title}, with a photo"


def _hasegawa():
    p = hasegawa.fetch("JT86")
    expect(p.get("item") == "09086", f"Hasegawa's JT86 page doesn't say item 09086 ({p.get('item')!r})")
    expect(p.get("image"), "Hasegawa's page has no box photo")
    return f"{p['title']} ({p.get('scale')})"


def _trumpeter():
    p = trumpeter.fetch("00968", photo=False)          # their search, then the page (no photo: two requests)
    expect(p.get("scale") == "1/16", f"Trumpeter's 00968 page doesn't say 1:16 ({p.get('scale')!r})")
    expect(p.get("barcode"), "Trumpeter's 00968 page has no barcode")
    return f"{p['title']} ({p['scale']})"


def _stedi():
    t = stedi.by_sku("MS-106")
    expect(t is not None, "Stedi's catalogue has no MS-106 nipper")
    expect(t["price_usd"], "Stedi's MS-106 has no price")
    return f"{t['name'][:60]} (US${t['price_usd']:.2f})"


def _hlj():
    found = hlj.search("4573102574039")
    expect(found, "HobbyLink Japan found nothing for the RX-78-2's barcode")
    return found[0]["title"]


def _goodgames():
    kits = goodgames.find("Combat Patrol Adeptus Mechanicus")
    expect(kits, "Good Games found no Combat Patrol: Adeptus Mechanicus")
    expect(any(k.get("code") for k in kits), "Good Games' kits have no GW code in their titles any more")
    return f"{len(kits)} kit(s), e.g. {kits[0].get('title')}"


def _gameology():
    games = gameology.search("Catan")
    expect(games, "Gameology found no Catan")
    expect(any(g.get("min_players") for g in games), "Gameology's games have no player counts (their BGG tags changed)")
    g = games[0]
    return f"{g['title']}: {g.get('min_players')}-{g.get('max_players')} players"


def _bluesky():
    shoes = bluesky.search("way of wade", limit=5)
    expect(shoes, "Blue Sky Athletics found no Way of Wade shoes")
    expect(any(s.get("price") for s in shoes), "Blue Sky's products have no prices")
    return f"{len(shoes)} shoe(s), e.g. {shoes[0]['name']}"


def _openlibrary():
    books = openlibrary.search("The Way of Kings Sanderson", limit=3)
    expect(books, "Open Library found no Way of Kings")
    expect(books[0].get("ol_work") and books[0].get("author"), "Open Library's results have no work id or author")
    return f"{books[0]['title']} by {books[0]['author']}"


def _steam_store():
    items = steam.store_search("Portal 2")
    expect(any(str(i.get("id")) == "620" for i in items), "Steam's store search didn't find Portal 2 (620)")
    return "Portal 2 found (app 620)"


def _steamhunters():
    g = steamhunters.game(620)
    expect(g and g.get("sh_median_minutes"), "SteamHunters has no median time for Portal 2")
    return f"Portal 2: median {g['sh_median_minutes']} min to 100%"


def _exophase():
    found = exophase.search("Portal 2", "steam")
    expect(found, "Exophase's search found no Portal 2")
    return found[0]["name"]


def _overpass():
    found = overpass.landmarks(overpass.near_line([(-27.4791, 152.9515)], 300))      # Constitution Hill, Mt Coot-tha
    expect(any(lm["kind"] == "peak" and lm["name"] for lm in found), "OpenStreetMap's Overpass found no named peak on Mt Coot-tha")
    peak = next(lm for lm in found if lm["kind"] == "peak" and lm["name"])
    return f"{peak['name']} ({peak['ele']} m)" if peak["ele"] else peak["name"]


def _commons():
    files = wikimedia.near(-27.4755, 152.9585, 1000, limit=10)
    expect(files, "Wikimedia Commons found no photos near the Mt Coot-tha lookout")
    info = wikimedia.images([f["title"] for f in files])
    expect(info and all(i["thumb"] for i in info.values()), "Wikimedia Commons' photos have no thumbnails")
    return f"{len(files)} photos nearby, {len(info)} with thumbnails"


def _bunnings():
    p = bunnings.fetch("https://www.bunnings.com.au/scotts-osmocote-10l-premium-plus-superior-potting-mix_p2962117")
    expect(p["bunnings_item"] == "2962117", f"Bunnings' page says item {p['bunnings_item']!r}, not 2962117")
    expect(p["price"] is not None, "Bunnings' product page has no price")
    expect(p["image"], "Bunnings' product page has no photo")
    return f"{p['name']}: ${p['price']:.2f}"


def _openmeteo():
    days = openmeteo.forecast(-27.47, 153.03, fresh=True)       # (never the kept copy: is Open-Meteo answering?)
    expect(days and days[0].get("max") is not None, "Open-Meteo's forecast has no temperatures")
    expect(openmeteo.find_place("Brisbane"), "Open-Meteo couldn't find Brisbane")
    return f"Brisbane today: {days[0]['max']:.0f}° max"


def _frankfurter():
    frankfurter._cache.clear()
    r = frankfurter.rates()
    expect(r["aud_per"].get("USD") and r["aud_per"].get("JPY"), "Frankfurter's rates have no USD or JPY")
    return f"1 USD = {r['aud_per']['USD']:.4f} AUD ({r['date']})"


def _lichess():
    a = lichess.explore("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "masters", fresh=True)    # (one cheap look-up)
    expect(a["total"] > 1000 and any(m["san"] == "e4" for m in a["moves"]), "Lichess' explorer has no e4 from the starting position")
    return f"{a['total']:,} master games from the start, e4 first"


# (site, what the app uses it for, the check)
CHECKS = [
    ("Tamiya", "paint and kit look-ups, photos", _tamiya),
    ("Hasegawa", "kit look-ups", _hasegawa),
    ("Trumpeter", "kit and tool look-ups", _trumpeter),
    ("Stedi", "model tool look-ups", _stedi),
    ("HobbyLink Japan", "Gundam (Bandai) kit look-ups", _hlj),
    # Good Games: paused (2026-10-18) - a small shop; the walk-through's runs got us asked to slow down. Its features
    # still work when you use them. Put this line back to check it weekly again.
    # ("Good Games", "Warhammer and Gundam kits, board games", _goodgames),
    ("Gameology", "board game facts", _gameology),
    ("Blue Sky Athletics", "Way of Wade shoes", _bluesky),
    ("Open Library", "books, covers, suggestions", _openlibrary),
    ("Steam store", "Find a game, Steam versions of Epic / Ubisoft games", _steam_store),
    ("SteamHunters", "time to 100%, unobtainable achievements", _steamhunters),
    ("Exophase", "DLC groups, Epic / Ubisoft games", _exophase),
    ("OpenStreetMap (Overpass)", "landmarks near a hike's track", _overpass),
    ("Wikimedia Commons", "photos near a hike's track and of its landmarks", _commons),
    ("Bunnings", "garden supplies and seeds from a product link", _bunnings),
    ("Open-Meteo", "weather tips for the balcony garden; places and weather for trips", _openmeteo),
    ("Frankfurter", "exchange rates for trips' money in other currencies", _frankfurter),
    ("Lichess explorer", "the chess opening trainer: what people play from a position", _lichess),
]
STATE = {"running": False}
_lock = threading.Lock()

SAVE = """
INSERT INTO site_checks (site, ok, detail, checked_at, failing_since)
VALUES (%(site)s, %(ok)s, %(detail)s, now(), CASE WHEN %(ok)s THEN NULL ELSE now() END)
ON CONFLICT (site) DO UPDATE SET ok = EXCLUDED.ok, detail = EXCLUDED.detail, checked_at = now(),
    failing_since = CASE WHEN EXCLUDED.ok THEN NULL ELSE COALESCE(site_checks.failing_since, now()) END"""


def run_all(only=None):
    """Check every site (or just the sites named in only), one after another; each result is saved as soon as it's known."""
    with _lock:
        if STATE["running"]:
            return
        STATE["running"] = True
    try:
        for site, _, check in CHECKS:
            if only is not None and site not in only:
                continue
            try:
                ok, detail = True, check()
            except Exception as e:  # noqa: BLE001 - any failure is the result we're after
                ok, detail = False, str(e) if isinstance(e, Unexpected) else f"{e.__class__.__name__}: {e}"
                log.warning("Site check failed for %s: %s", site, detail)
            with db() as conn:
                conn.execute(SAVE, {"site": site, "ok": ok, "detail": (detail or "")[:500]})
                conn.execute("INSERT INTO site_check_log (site, ok, detail) VALUES (%s, %s, %s)", (site, ok, (detail or "")[:500]))
        with db() as conn:            # (a year of history is plenty)
            conn.execute("DELETE FROM site_check_log WHERE checked_at < now() - interval '1 year'")
    finally:
        STATE["running"] = False


def _wanted_prices():
    """With the weekly check: wanted Blue Sky gear's price and stock (wanted_more.refresh_weekly)."""
    from . import wanted_more
    try:
        wanted_more.refresh_weekly()
    except Exception:  # noqa: BLE001 - a shop down is no reason to stop
        log.exception("Weekly wanted-price refresh failed")


def failing() -> list[str]:
    """The sites (still checked) whose last result was a failure."""
    names = [site for site, _, _ in CHECKS]
    with db() as conn:
        rows = conn.execute("SELECT site FROM site_checks WHERE NOT ok AND site = ANY(%s)", (names,)).fetchall()
    return [r["site"] for r in rows]


def due():
    """What the 6-hourly look should do: 'all' (a site never checked, or the oldest result a week old), the list of
    sites that failed more than a day ago (asked again on their own: a one-off timeout clears itself), or None.
    Only the sites still in CHECKS count: a paused site's old row (Good Games, 16 Oct) made every result look a week
    old, and the whole check ran every 6 hours (found 2026-11-16)."""
    names = [site for site, _, _ in CHECKS]
    with db() as conn:
        rows = conn.execute("SELECT site, ok, checked_at FROM site_checks WHERE site = ANY(%s)", (names,)).fetchall()
    now = datetime.now(timezone.utc)
    if len(rows) < len(names) or now - min(r["checked_at"] for r in rows) > WEEKLY:
        return "all"
    retry = [r["site"] for r in rows if not r["ok"] and now - r["checked_at"] > RETRY]
    return retry or None


def start_weekly():
    """While the app runs: looked at every 6 hours - the whole check once a week, a failed site again a day later."""
    def loop():
        while True:
            try:
                todo = due()
                if todo == "all":
                    run_all()
                    _wanted_prices()
                elif todo:
                    run_all(only=todo)
            except Exception:  # database restarting...: say so, try again later
                log.exception("Weekly site check failed")
            threading.Event().wait(6 * 3600)
    threading.Thread(target=loop, daemon=True, name="site-check-weekly").start()


@router.get("/site-checks")
def site_checks():
    with db() as conn:
        rows = {r["site"]: r for r in conn.execute("SELECT * FROM site_checks").fetchall()}
        # the last 30 days: how many checks, how many failed (site_check_log, kept since 2026-11-17)
        month = {r["site"]: r for r in conn.execute(
            "SELECT site, count(*) AS checks, count(*) FILTER (WHERE NOT ok) AS failed FROM site_check_log "
            "WHERE checked_at > now() - interval '30 days' GROUP BY site").fetchall()}
    empty = {"ok": None, "detail": None, "checked_at": None, "failing_since": None}
    sites = [{"site": site, "used_for": what,
              **({k: rows[site][k] for k in empty} if site in rows else empty),
              "checks_30d": month[site]["checks"] if site in month else 0,
              "failed_30d": month[site]["failed"] if site in month else 0} for site, what, _ in CHECKS]
    return {"sites": sites, "running": STATE["running"], "failing": sum(1 for s in sites if s["ok"] is False),
            "last_run": max((s["checked_at"] for s in sites if s["checked_at"]), default=None)}


@router.post("/site-checks/run", status_code=202)
def run_now(tasks: BackgroundTasks):
    if not STATE["running"]:
        tasks.add_task(run_all)
    return {"running": True}
