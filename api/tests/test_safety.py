"""Safety checks across the API: what it accepts, what it serves, and that it copes with
requests arriving together. Added in the review of 2026-10-14."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from app.calendar import days_of
from app.images import MAX_PHOTO_BYTES, fetched_photo
from app.spending import cell


# ---------------------------------------------------------------- links shown as links
def test_only_web_links_are_saved_where_they_become_links(client):
    for bad in ("javascript:alert(1)", "data:text/html,hi", "boardgamegeek.com/game/13"):
        assert client.post("/api/board-games", json={"name": "Catan", "bgg_url": bad}).status_code == 422, bad
        assert client.post("/api/volleyball/videos", json={"title": "x", "url": bad}).status_code == 422, bad
    game = client.post("/api/board-games", json={"name": "Catan",
                                                 "bgg_url": "https://boardgamegeek.com/boardgame/13/catan"})
    assert game.status_code == 201
    url = f"/api/board-games/{game.json()['game_id']}"
    assert client.patch(url, json={"bgg_url": "javascript:alert(1)"}).status_code == 422
    assert client.patch(url, json={"bgg_url": None}).json()["bgg_url"] is None


# ---------------------------------------------------------------- photos in and out
def test_uploads_must_be_real_photo_types_and_small_enough(client):
    game = client.post("/api/board-games", json={"name": "Catan"}).json()
    url = f"/api/board-games/{game['game_id']}/photo"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert client.put(url, content=svg, headers={"Content-Type": "image/svg+xml"}).status_code == 415
    assert client.put(url, content=b"<html>", headers={"Content-Type": "text/html"}).status_code == 415
    too_big = b"\xff\xd8" + b"0" * MAX_PHOTO_BYTES
    assert client.put(url, content=too_big, headers={"Content-Type": "image/jpeg"}).status_code == 413
    assert client.put(url, content=b"", headers={"Content-Type": "image/jpeg"}).status_code == 422


def test_photos_are_served_as_photos_and_cached(client):
    game = client.post("/api/board-games", json={"name": "Catan"}).json()
    url = f"/api/board-games/{game['game_id']}/photo"
    client.put(url, content=b"\xff\xd8box", headers={"Content-Type": "image/jpeg"})
    r = client.get(url)
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in r.headers["cache-control"]
    # ...and a new photo gets a new address, so the year-long cache never shows an old one
    before = client.get(f"/api/board-games/{game['game_id']}").json()["photo_url"]
    client.put(url, content=b"\xff\xd8new", headers={"Content-Type": "image/jpeg"})
    assert client.get(f"/api/board-games/{game['game_id']}").json()["photo_url"] != before


def photo(content_type, body=b"\xff\xd8img", status=200):
    return httpx.Response(status, content=body, headers={"content-type": content_type})


def test_photos_from_other_sites_are_checked_too():
    assert fetched_photo(photo("image/jpeg")) == (b"\xff\xd8img", "image/jpeg")
    assert fetched_photo(photo("image/png; charset=binary")) == (b"\xff\xd8img", "image/png")
    assert fetched_photo(photo("image/svg+xml", b"<svg/>")) == (None, None)      # could carry script
    assert fetched_photo(photo("text/html")) == (None, None)
    assert fetched_photo(photo("image/jpeg", status=404)) == (None, None)
    assert fetched_photo(photo("image/jpeg", b"0" * (MAX_PHOTO_BYTES + 1))) == (None, None)


# ---------------------------------------------------------------- CSV exports
def test_csv_cells_never_run_as_formulas():
    assert cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert [cell(v) for v in ("+1", "-2", "@SUM(A1)", "\tx")] == ["'+1", "'-2", "'@SUM(A1)", "'\tx"]
    assert [cell(v) for v in ("Flat Black", "", None, -3, 3.95)] == ["Flat Black", "", None, -3, 3.95]


def test_csv_export_of_every_hobby(client):
    client.post("/api/board-games", json={"name": "=cmd|' /C calc'!A0", "status": "Owned"})
    client.post("/api/volleyball/games", json={"opponent": "Spikers", "sets_won": 3, "sets_lost": 0})
    client.post("/api/gear", json={"name": "Knee pads"})
    games = client.get("/api/export/board-games.csv")
    assert games.status_code == 200
    assert "off-the-clock-board-games-" in games.headers["content-disposition"]
    assert "\n'=cmd" in games.content.decode("utf-8-sig")                       # made harmless
    assert "Spikers" in client.get("/api/export/volleyball.csv").text
    assert "Knee pads" in client.get("/api/export/gear.csv").text
    assert client.get("/api/export/plays.csv").status_code == 200


# ---------------------------------------------------------------- many requests at once
def test_requests_arriving_together_each_get_a_connection(client):
    """The connection pool: twenty requests at once, some writing, all answered correctly."""
    def add(i):
        return client.post("/api/board-games", json={"name": f"Game {i:02}"}).status_code

    def read(_):
        return client.get("/api/board-games").status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(add, range(20))) + list(pool.map(read, range(20)))
    assert set(codes[:20]) == {201} and set(codes[20:]) == {200}
    assert len(client.get("/api/board-games").json()) == 20


def test_a_failed_request_leaves_nothing_half_done(client):
    """A request that fails part-way rolls back, and the pooled connection is fine for the next one."""
    game = client.post("/api/board-games", json={"name": "Catan"}).json()
    r = client.patch(f"/api/board-games/{game['game_id']}", json={"min_players": 6, "max_players": 2})
    assert r.status_code == 422
    after = client.get(f"/api/board-games/{game['game_id']}").json()
    assert (after["min_players"], after["max_players"]) == (None, None)


# ---------------------------------------------------------------- calendar repeats, edge cases
def event(**kw):
    return {"starts_on": date(2026, 10, 6), "repeats": "never", "repeat_until": None, "skipped": [], **kw}


def test_repeating_days_respect_the_end_and_skips():
    weekly = event(repeats="weekly", repeat_until=date(2026, 10, 20), skipped=[date(2026, 10, 13)])
    assert days_of(weekly, date(2026, 10, 1), date(2026, 12, 31)) == [date(2026, 10, 6), date(2026, 10, 20)]
    fortnightly = event(repeats="fortnightly")
    assert days_of(fortnightly, date(2026, 10, 7), date(2026, 10, 21)) == [date(2026, 10, 20)]
    assert days_of(fortnightly, date(2026, 10, 21), date(2026, 11, 2)) == []     # next one is 3 Nov
    assert days_of(event(), date(2026, 10, 6), date(2026, 10, 6)) == [date(2026, 10, 6)]
    assert days_of(event(), date(2026, 10, 7), date(2026, 10, 30)) == []
    assert days_of(event(repeats="weekly"), date(2026, 9, 1), date(2026, 10, 5)) == []   # before it starts
