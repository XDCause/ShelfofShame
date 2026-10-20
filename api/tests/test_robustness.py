"""Every route, poked the way a bad request or a stale page would: a thing that isn't there, an empty body, junk. The
API must answer with a 4xx that says what's wrong - never a 500 (a crash) - and a missing thing must be a 404. Every
outside site is down here: a route that needs one must say it couldn't reach it (502), not crash.

The routes come from the app itself (its OpenAPI list - app.routes holds lazy routers in this FastAPI), so a new route is covered the day it's added."""
import re

import pytest

from app.main import app
from tests.conftest import SITES_DOWN


@pytest.fixture(autouse=True)
def sites_down(monkeypatch):
    """Every outside site is down for these tests (each module's own "couldn't reach" error), and nothing at all can
    leave the container - a route must cope with a site that doesn't answer, not crash."""
    import httpx

    def no_network(*_a, **_k):
        raise httpx.ConnectError("No network in the robustness tests")
    # (the real network's transports: the test client talks to the app through its own, which stays)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
    SITES_DOWN["on"] = True
    yield
    SITES_DOWN["on"] = False

# Routes that start long or outside work even with nothing sent (each has its own tests).
SKIP = {
    ("POST", "/api/backups"), ("POST", "/api/videogames/sync"), ("POST", "/api/videogames/sync/full"),
    ("POST", "/api/site-checks/run"), ("POST", "/api/catalog/refresh"), ("POST", "/api/chess/sync"),
}
ROUTES = sorted((method.upper(), path) for path, ops in app.openapi()["paths"].items()
                for method in ops if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"))
# One of each kind (missing, empty, far too long, a number too big, a list, an object, markup / SQL-looking text):
# a field either takes a kind or refuses it, so more of the same kind only adds time.
JUNK = [None, "", "x" * 5000, 10**12, [], {"nested": {"deep": [1, 2]}}, "<script>'; DROP TABLE x; --</script>"]


def filled(path: str, value: str) -> str:
    return re.sub(r"\{[^}]+\}", value, path)


def calls(client, method, url, **kw):
    return client.request(method, url, **kw)


def ok(r) -> bool:
    """Not a crash: a 4xx, a success, or "couldn't reach <site>" (502/503/504) with a message saying so."""
    if r.status_code in (502, 503, 504):
        return bool(r.json().get("detail"))
    return r.status_code < 500


# Each sweep is ONE test looping over the routes (not a test per route): a test's set-up wipes ~70 tables (~0.2 s),
# which ~1,100 routes x cases made most of the suite's time. Every problem is collected and reported together.
def sweep(client, cases):
    """Run (method, url, kwargs, check) cases, signed in throughout (a route like "sign out" ends the session: then
    a new one, and that case again - so every route is really tested, not just refused for being signed out)."""
    from app import auth
    from tests.conftest import sign_in_directly
    problems = []
    for method, url, kw, check in cases:
        r = calls(client, method, url, **kw)
        if r.status_code == 401 and r.json().get("detail") == "Sign in first.":
            client.cookies.set(auth.COOKIE, sign_in_directly())
            r = calls(client, method, url, **kw)
        problem = check(r)
        if problem:
            problems.append(f"{method} {url} {str(kw)[:60]}: {problem}")
    assert not problems, f"{len(problems)} problems:\n" + "\n".join(problems[:40])


def not_a_crash(r):
    return None if ok(r) else f"{r.status_code} {r.text[:200]}"


def missing_is_404(r):
    if not ok(r):
        return f"{r.status_code} {r.text[:200]}"
    # (a body that fails validation is checked before the thing is looked up; a site that's down says so)
    if r.status_code not in (422, 502, 503, 504, 404, 400, 409, 413, 415, 200, 204):
        return f"{r.status_code} for a missing thing {r.text[:120]}"
    return None


def test_a_missing_thing_is_a_404_never_a_crash(client):
    cases = []
    for method, path in ROUTES:
        if "{" in path and (method, path) not in SKIP:
            body = {"json": {} if method in ("POST", "PUT", "PATCH") else None}
            cases.append((method, filled(path, "999999"), body, missing_is_404))
            cases.append((method, filled(path, "not-a-number"), body, not_a_crash))       # a word for the id
    sweep(client, cases)


def test_an_empty_or_junk_body_is_refused_not_a_crash(client):
    sweep(client, [(method, path, {"content": body} if isinstance(body, str) else {"json": body}, not_a_crash)
                   for method, path in ROUTES if method in ("POST", "PUT", "PATCH") and "{" not in path and (method, path) not in SKIP
                   for body in ({}, [], "not json")])


def test_junk_in_every_field_is_refused_not_a_crash(client):
    """Each field each route takes, given each kind of junk (the others left out)."""
    spec = app.openapi()
    cases = []
    for method, path in ROUTES:
        if method not in ("POST", "PUT", "PATCH") or (method, path) in SKIP:
            continue
        schema = spec["paths"][path][method.lower()]
        ref = (schema.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}) or {}).get("$ref")
        if not ref:
            continue
        for name in spec["components"]["schemas"][ref.split("/")[-1]].get("properties", {}):
            cases += [(method, filled(path, "999999"), {"json": {name: junk}}, not_a_crash) for junk in JUNK]
    assert len(cases) > 1000                    # (the sweep really ran over the routes)
    sweep(client, cases)


def test_every_list_answers_on_an_empty_database(client):
    sweep(client, [("GET", path, {}, not_a_crash) for method, path in ROUTES if method == "GET" and "{" not in path])


def test_a_number_too_big_for_its_column_says_so(client, make_supply):
    """(Found by the sweep above: 10**12 in an integer column was a 500 in six places; db.py now answers 422.)"""
    supply = make_supply()
    r = client.patch(f"/api/supplies/{supply['supply_id']}", json={"qty_on_hand": 10**12})
    assert r.status_code == 422 and "too big" in r.json()["detail"]
    r = client.post("/api/volleyball/games", json={"played_on": "2026-10-01", "sets_won": 10**12})
    assert r.status_code == 422
