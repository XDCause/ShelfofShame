"""End-to-end walk-through of Off the Clock in a real (headless) browser.

Outside websites (shops, Steam, Bunnings...) are stand-ins in the copy this runs against (OUTSIDE_SITES=stand-ins,
api/app/stand_ins.py): no step asks a real site. The weekly site check is what looks at the real ones.

Run it with .\\run_e2e.ps1 (backs up first and restores afterwards - this script changes data).
Runs inside the Playwright container on the app's Docker network, against http://web.
The shared part: set-up, helpers and the step decorator; the steps are in wt_<area>.py and the run in
walkthrough.py (split 2026-10-21, health check). Prints a PASS/FAIL line per step, all browser errors, and saves screenshots to /out.
Written against the user's real data (the Zero and P-40E models, XF-1 etc.); item counts are
read from the API at the start, so adding or removing supplies doesn't break it.
"""
import base64
import http.cookiejar
import os
import ssl
import json
import re
import struct
import time
import urllib.parse
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = "https://web"          # (the copy's own certificate: the browser and urllib are told not to check it)
OUT = "/out"
results, errors = [], []

# Signed in (api/app/auth.py): run_e2e.ps1 set this copy's password (E2E_PASSWORD) - its own, never yours.
PASSWORD = os.environ["E2E_PASSWORD"]
_tls = ssl.create_default_context()
_tls.check_hostname, _tls.verify_mode = False, ssl.CERT_NONE
_jar = http.cookiejar.CookieJar()
_api = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_tls), urllib.request.HTTPCookieProcessor(_jar))
_api.open(urllib.request.Request(f"{BASE}/api/auth/login", data=json.dumps({"password": PASSWORD}).encode(),
                                 headers={"Content-Type": "application/json"}))
# (the cookie's name depends on the copy - otc_session, otc_session_dev: auth.COOKIE - so it's taken from the answer)
COOKIE = next(c.name for c in _jar if c.name.startswith("otc_session"))
TOKEN = next(c.value for c in _jar if c.name == COOKIE)


def get_json(path):
    """A signed-in read of the API."""
    return json.load(_api.open(f"{BASE}{path}"))


def signed_in(context):
    """A browser context with this run's session cookie (as if signed in)."""
    context.add_cookies([{"name": COOKIE, "value": TOKEN, "url": BASE, "secure": True, "httpOnly": True,
                          "sameSite": "Strict"}])
    return context


# How many supplies there are right now (and how many are Paint), for the list checks.
_supplies = get_json("/api/supplies")
TOTAL = len(_supplies)
PAINTS = sum(s["category"] == "Paint" for s in _supplies)
MODELS = len(get_json("/api/models"))
CHESS = bool(get_json("/api/chess/account")["username"])   # Home gets a rating tile
CHESS_PUZZLES = CHESS and bool((get_json("/api/chess/summary").get("puzzles") or {}).get("highest"))   # ...and a puzzle one
_reading = get_json("/api/reading/summary")
READING = (any(_reading["counts"].values())) + bool(_reading["reading"])   # Home: books this year (+ reading now)
HIKING = bool(get_json("/api/hiking/summary")["all_time"]["hikes"])   # Home: km hiked
_garden = get_json("/api/garden/summary")
GARDEN = bool(_garden["growing"] or _garden["spaces"])                                  # Home: plants growing
SHOOTING = bool(get_json("/api/shooting/summary")["all_time"]["sessions"])   # Home: rounds this year
_travel = get_json("/api/travel/summary")
TRAVEL = bool(_travel["now"] or _travel["upcoming"] or _travel["countries_been"])          # Home: the next trip / countries
MARK = f"e2e{int(time.time())}"   # a word only this run's journal page contains


# Anything not from the app's own copy (https://web) - book covers, video thumbnails, shop pictures - gets a stand-in
# answer: a 1-pixel picture for images, an empty reply for the rest. The tests never ask outside sites (CLAUDE.md), and
# an outage elsewhere (Open Library's covers, 2026-10-22) mustn't fail the run.
OUTSIDE = re.compile(r"^https?://(?!web(?::\d+)?/)")
ONE_PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def offline(route):
    if route.request.resource_type == "image":
        route.fulfill(status=200, content_type="image/png", body=ONE_PIXEL)
    else:
        route.fulfill(status=204, body="")


NOW = {"step": "start"}   # the step running, so a browser error says where it happened


STEPS = {}   # every @step function by name (walkthrough.py checks each is in its run order)


def step(name):
    def wrap(fn):
        def run(page, *a):
            t = time.time()
            NOW["step"] = name.split(":")[0]
            try:
                fn(page, *a)
                results.append((name, "PASS", f"{time.time() - t:.1f}s"))
            except Exception as e:  # keep going: one broken step shouldn't hide the rest
                first = (str(e).splitlines() or ["(no message)"])[0]   # a bare assert has none: that crashed the run
                results.append((name, "FAIL", f"{type(e).__name__}: {first[:220]}"))
                safe = re.sub(r"\W+", "_", name)
                try:
                    page.screenshot(path=f"{OUT}/FAIL_{safe}.png", full_page=True)
                except Exception:
                    pass
                page.keyboard.press("Escape")
        STEPS[fn.__name__] = run
        return run
    return wrap


def shot(page, name, full=True):
    page.screenshot(path=f"{OUT}/{name}.png", full_page=full)


def drawer(page):
    return page.locator("aside.drawer")


def go(page, name):
    """Open a page from the navigation: the sidebar on desktop, the tab bar on phones (only one
    of them is visible, so the link name is enough). A hobby's own pages (Colours) are tabs at
    the top of the hobby, so go to the hobby first."""
    if name in SECTION_TABS:
        go(page, SECTION_TABS[name])
        page.locator(".section-tabs").get_by_role("link", name=name, exact=True).click()
    else:      # (the navigation's own link: a page can have another with the same name - Home's Supplies card)
        page.locator(".sidebar, .tabbar").get_by_role("link", name=name, exact=True).click()


SECTION_TABS = {"Colours": "Models", "Plays": "Board games", "Gear": "Volleyball", "Videos": "Volleyball"}


def watch(page, label):
    page.route(OUTSIDE, offline)                       # (no outside site, ever)
    # (a wrong password's 401 from /api/auth/login is expected in the sign-in step: the browser logs it as an error too;
    # "Failed to load resource: net::ERR_FAILED" says no more than requestfailed below, which names the address)
    page.on("console", lambda m: m.type == "error" and "status of 401" not in m.text
            and "Failed to load resource: net::ERR_FAILED" not in m.text and errors.append(f"[{label}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{label}] page error: {e}"))
    # Every failed request names its address (the browser's own "Failed to load resource" line doesn't).
    page.on("response", lambda r: r.status >= 400 and not (r.status == 401 and "/api/auth/login" in r.url)
            and errors.append(f"[{label}] HTTP {r.status} {r.url}"))
    # A request with no answer at all (net::ERR_FAILED, refused, reset) has no response either: name it and the step.
    # Not counted: ERR_ABORTED (the page moved on before it came back) and ERR_BLOCKED_BY_ORB (an outside site's
    # picture - the stand-ins' made-up addresses - that this offline copy can't fetch). ERR_FAILED always counts: it
    # once looked like a page change cancelling requests, and was really nginx dropping 1 request in 1000 (HISTORY 5b).
    page.on("requestfailed", lambda r: not any(x in (r.failure or "") for x in ("ERR_ABORTED", "ERR_BLOCKED_BY_ORB"))
            and errors.append(f"[{label}] {NOW['step']}: {r.method} {r.url} - {r.failure}"))


# ---------------------------------------------------------------- desktop


# ---------------------------------------------------------------- new in the kit-stash update
# A 1x1 PNG for the build-log photo.
PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


# (imported here for the step files, which take everything from this one)
SHARED = (struct, expect, sync_playwright)
