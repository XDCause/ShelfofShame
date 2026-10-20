"""Screenshots for the showcase (showcase.ps1): the same pages of one version of the app, at laptop and phone size.

    python showcase.py <base url> <version label>      (E2E_PASSWORD: the showcase copy's password)

Saves /out/<label>/<page>_<size>.jpg. A page the version hasn't got yet still gets a picture (its "not found" or Home):
the gallery leaves out pages whose module didn't exist (showcase.ps1 knows from git).
"""
import http.cookiejar
import json
import os
import ssl
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
OUT = f"/out/{LABEL}"
PAGES = [("home", "/"), ("supplies", "/supplies"), ("models", "/models"), ("boardgames", "/boardgames"),
         ("volleyball", "/volleyball"), ("videogames", "/videogames"), ("chess", "/chess"), ("reading", "/reading"),
         ("hiking", "/hiking"), ("gardening", "/gardening"), ("shooting", "/shooting"), ("travel", "/travel"),
         ("goals", "/goals"), ("journal", "/journal"), ("calendar", "/calendar")]
SIZES = {"pc": dict(viewport={"width": 1440, "height": 900}),
         "phone": dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)}
# A version's own address for a page (PATHS="supplies=/models/inventory;..."): Supplies lived under Models at first.
PAGES = [(k, dict(x.split("=", 1) for x in os.environ.get("PATHS", "").split(";") if "=" in x).get(k, p)) for k, p in PAGES]
TALLEST = {"pc": 2400, "phone": 2600}      # a long page is cut here: enough to show what's where


def session_token():
    tls = ssl.create_default_context()
    tls.check_hostname, tls.verify_mode = False, ssl.CERT_NONE
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls), urllib.request.HTTPCookieProcessor(jar))
    opener.open(urllib.request.Request(os.environ.get("API_BASE", BASE) + "/api/auth/login",
                                       data=json.dumps({"password": os.environ["E2E_PASSWORD"]}).encode(),
                                       headers={"Content-Type": "application/json"}))
    return next(c for c in jar if c.name.startswith("otc_session"))      # otc_session, otc_session_dev...: auth.COOKIE


os.makedirs(OUT, exist_ok=True)
cookie = session_token()
with sync_playwright() as p:
    browser = p.chromium.launch()
    for size, kw in SIZES.items():
        ctx = browser.new_context(ignore_https_errors=True, color_scheme="light", reduced_motion="reduce",
                                  timezone_id="Australia/Brisbane", locale="en-AU", **kw)
        ctx.add_cookies([{"name": cookie.name, "value": cookie.value, "url": BASE, "secure": True, "httpOnly": True, "sameSite": "Strict"}])
        page = ctx.new_page()
        for key, path in PAGES:
            try:
                page.goto(BASE + path, wait_until="networkidle", timeout=30000)
            except Exception:
                pass                                   # (a map's tiles never go quiet: take it as it is)
            page.wait_for_timeout(1200)                # fonts, pictures, the last numbers
            # the whole page at its normal window size (a taller window would stretch what's sized to the screen)
            height = min(page.evaluate("document.documentElement.scrollHeight"), TALLEST[size])
            page.screenshot(path=f"{OUT}/{key}_{size}.jpg", type="jpeg", quality=82, full_page=True,
                            clip={"x": 0, "y": 0, "width": kw["viewport"]["width"], "height": max(height, kw["viewport"]["height"])})
            print(f"  {LABEL} {size} {key}", flush=True)
        ctx.close()
    browser.close()
