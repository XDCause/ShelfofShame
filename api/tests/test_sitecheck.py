"""The weekly check of the websites the app reads: results saved per site, failing_since kept while it
keeps failing and cleared when it works again. The checks themselves are faked (no real sites)."""
from app import sitecheck


def fake(results):
    """CHECKS whose checks return / raise what `results` says, in order."""
    def check_for(site):
        def check():
            r = results[site]
            if isinstance(r, Exception):
                raise r
            return r
        return check
    return [(site, "for testing", check_for(site)) for site in results]


def test_results_and_failing_since(client, monkeypatch):
    assert client.get("/api/site-checks").json()["sites"][0]["ok"] is None        # never checked yet
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "XF-1 Flat Black, with a photo",
                                                   "Gameology": sitecheck.Unexpected("no player counts")}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert (got["Tamiya"]["ok"], got["Tamiya"]["detail"]) == (True, "XF-1 Flat Black, with a photo")
    assert (got["Gameology"]["ok"], got["Gameology"]["detail"]) == (False, "no player counts")
    since = got["Gameology"]["failing_since"]
    assert since and got["Tamiya"]["failing_since"] is None
    assert client.get("/api/site-checks").json()["failing"] == 1
    # Still failing a week later: failing_since stays the first day. A crash counts as a failure too.
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "ok", "Gameology": TimeoutError("timed out")}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert got["Gameology"]["failing_since"] == since and got["Gameology"]["detail"] == "TimeoutError: timed out"
    # Working again: cleared.
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "ok", "Gameology": "Catan: 3-4 players"}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert got["Gameology"]["ok"] and got["Gameology"]["failing_since"] is None


def test_run_now_starts_it(client, monkeypatch):
    ran = []
    monkeypatch.setattr(sitecheck, "run_all", lambda: ran.append(1))
    assert client.post("/api/site-checks/run").status_code == 202
    assert ran == [1]


def test_every_real_check_is_listed():
    assert len({site for site, _, _ in sitecheck.CHECKS}) == len(sitecheck.CHECKS) >= 10


# ---------------------------------------------------------------- each check knows a good answer from a changed one
import pytest  # noqa: E402

from app import (bluesky, bunnings, exophase, frankfurter, gameology, goodgames, hasegawa, hlj, openlibrary,  # noqa: E402
                 openmeteo, overpass, steam, steamhunters, stedi, tamiya, trumpeter, wikimedia)

# check -> (what to fake, a good answer, a changed answer): the site's module function, faked both ways
CASES = {
    "_tamiya": ((tamiya, "fetch"), {"title": "Acrylic Mini XF-1 Flat Black", "image": b"jpg"}, {"title": "Something else"}),
    "_hasegawa": ((hasegawa, "fetch"), {"item": "09086", "image": b"jpg", "title": "A6M5", "scale": "1/48"}, {"item": "1"}),
    "_trumpeter": ((trumpeter, "fetch"), {"scale": "1/16", "barcode": "9580208009682", "title": "Tiger"}, {"scale": "1/16"}),
    "_stedi": ((stedi, "by_sku"), {"name": "Precision nipper", "price_usd": 25.0}, None),
    "_hlj": ((hlj, "search"), [{"title": "HG RX-78-2"}], []),
    "_goodgames": ((goodgames, "find"), [{"code": "71-71", "title": "Combat Patrol"}], [{"title": "Combat Patrol"}]),
    "_gameology": ((gameology, "search"), [{"title": "Catan", "min_players": 3, "max_players": 4}], [{"title": "Catan"}]),
    "_bluesky": ((bluesky, "search"), [{"name": "Way of Wade 12", "price": 289.99}], [{"name": "Way of Wade 12"}]),
    "_openlibrary": ((openlibrary, "search"), [{"ol_work": "OL1W", "author": "Brandon Sanderson", "title": "The Way of Kings"}],
                     [{"title": "The Way of Kings"}]),
    "_steam_store": ((steam, "store_search"), [{"id": 620, "name": "Portal 2"}], [{"id": 400}]),
    "_steamhunters": ((steamhunters, "game"), {"sh_median_minutes": 900}, {"sh_median_minutes": None}),
    "_exophase": ((exophase, "search"), [{"name": "Portal 2"}], []),
    "_overpass": ((overpass, "landmarks"), [{"kind": "peak", "name": "Constitution Hill", "ele": "287"}], [{"kind": "lookout", "name": "x"}]),
    "_bunnings": ((bunnings, "fetch"), {"bunnings_item": "2962117", "price": 12.98, "image": "https://x/i.jpg", "name": "Osmocote"},
                  {"bunnings_item": "2962117", "price": None, "image": "u", "name": "x"}),
    "_frankfurter": ((frankfurter, "rates"), {"aud_per": {"USD": 1.52, "JPY": 0.0101}, "date": "2026-10-21"}, {"aud_per": {"USD": 1.5}}),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_check_passes_a_good_answer_and_catches_a_changed_one(name, monkeypatch):
    (module, fn), good, changed = CASES[name]
    check = getattr(sitecheck, name)
    if name == "_overpass":                                  # (it builds its query with near_line first)
        monkeypatch.setattr(overpass, "near_line", lambda *a, **k: "around:300")
    monkeypatch.setattr(module, fn, lambda *a, **k: good)
    said = check()
    assert isinstance(said, str) and said                                       # what it found, for Settings
    monkeypatch.setattr(module, fn, lambda *a, **k: changed)
    with pytest.raises(sitecheck.Unexpected):
        check()


def test_the_checks_that_ask_twice(monkeypatch):
    """Wikimedia (photos, then their thumbnails) and Open-Meteo (a forecast, then a place)."""
    monkeypatch.setattr(wikimedia, "near", lambda *a, **k: [{"title": "File:Lookout.jpg"}])
    monkeypatch.setattr(wikimedia, "images", lambda titles: {"File:Lookout.jpg": {"thumb": "https://x/t.jpg"}})
    assert "1 photos nearby" in sitecheck._commons()
    monkeypatch.setattr(wikimedia, "images", lambda titles: {"File:Lookout.jpg": {"thumb": None}})
    with pytest.raises(sitecheck.Unexpected):
        sitecheck._commons()
    monkeypatch.setattr(openmeteo, "forecast", lambda *a, **k: [{"max": 27.4}])
    monkeypatch.setattr(openmeteo, "find_place", lambda q: [{"name": "Brisbane"}])
    assert sitecheck._openmeteo() == "Brisbane today: 27° max"
    monkeypatch.setattr(openmeteo, "find_place", lambda q: [])
    with pytest.raises(sitecheck.Unexpected):
        sitecheck._openmeteo()


def test_every_check_has_a_test():
    tested = set(CASES) | {"_commons", "_openmeteo", "_goodgames"}
    assert {check.__name__ for _, _, check in sitecheck.CHECKS} <= tested


def test_a_second_run_waits_for_the_first(monkeypatch):
    calls = []
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "ok"}))
    monkeypatch.setitem(sitecheck.STATE, "running", True)                      # one already running
    monkeypatch.setattr(sitecheck, "db", lambda: calls.append(1))
    sitecheck.run_all()
    assert calls == [] and sitecheck.STATE["running"] is True


def test_the_weekly_price_refresh_never_stops_the_check(monkeypatch):
    from app import wanted_more
    monkeypatch.setattr(wanted_more, "refresh_weekly", lambda: (_ for _ in ()).throw(RuntimeError("shop down")))
    sitecheck._wanted_prices()                                                   # (logged, not raised)
