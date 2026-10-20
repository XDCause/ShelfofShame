"""UI audit: every page (and a sample of panels) at five screen widths in both themes, checked for the problems a
person notices - and the walk-through doesn't look for:

  overflow     the page scrolls sideways, or something pokes out past the screen's edge
  clipped      text cut off or spilling out of its box (deliberate "..." truncation is fine)
  overlap      two buttons / links on top of each other, or two pieces of text on top of each other
  small        a touch target under 24 x 24 px on a phone (WCAG 2.2 target size; inline links in text are fine)
  image        an image that didn't load
  art          a drawn banner with a tree off its hill (floating in the sky / sea); a gallery of every banner is saved too
  a11y         axe-core's accessibility rules (contrast, names, roles, landmarks...), serious and critical only
  console      browser errors and failed requests while the page was open

Run by run_e2e.ps1 after the walk-through, on the same throwaway copy (http://web, stand-ins for outside sites).
Read only: it opens pages and panels and presses Escape, nothing else. One process per screen size, side by side. Writes /out/ui_audit.json and a screenshot per
problem page (outlined in red: /out/audit_*.png). Exits 1 if it finds anything not in ACCEPTED.

    python /e2e/ui_audit.py              # everything
    python /e2e/ui_audit.py /models      # only pages whose address starts with this
"""
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import ssl
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "https://web"          # (the copy's own certificate: not checked)
OUT = "/out"
AXE = "/usr/local/lib/python3.10/dist-packages/axe_playwright_python/axe.min.js"
ONLY = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ""

SIZES = [("pc", 1440, 900, False), ("laptop", 1024, 768, False), ("tablet", 768, 1024, True),
         ("phone", 390, 844, True), ("narrow", 320, 640, True)]
THEMES = ["light", "dark"]
AXE_SIZES = ("pc", "phone")      # colour and names don't change with width: axe at two sizes is enough (and it's slow)
# Panels worth a look: (page, what to click to open one). Clicked only if it's there.
PANELS = [("/supplies", "tr.row"), ("/models/kits", ".model-card"), ("/reading/books", ".book-card"),
          ("/boardgames/games", ".bg-card, .board-game-card, .game-card"), ("/videogames/games", ".game-row"),
          ("/travel/trips", ".trip-card, .row-button"), ("/calendar", ".cal-day, .calendar-day")]
# Problems looked at and accepted (a key: "kind|selector"), with why.
ACCEPTED = {
    # axe can't see the banner picture behind the clear nav bar, so it measures the search box's light text against
    # the page colour; over the (always dark) banner it's ~9:1, and once scrolled the bar is solid with dark text.
    "a11y|color-contrast: nav bar over the banner": "over the banner",
}

# The checks, run in the page. Returns [{kind, selector, detail, rect}].
CHECKS = r"""
() => {
  const W = innerWidth, out = [];
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return false;
    const closed = el.closest('details:not([open])');
    if (closed && !el.closest('summary')?.parentElement?.isSameNode(closed)) return false;   // inside a closed <details>
    for (let p = el; p; p = p.parentElement) {
      const ps = getComputedStyle(p);
      if (ps.display === 'none' || ps.visibility === 'hidden' || ps.contentVisibility === 'hidden') return false;
      if (p.getAttribute('aria-hidden') === 'true' && p.tagName !== 'svg' && p.closest('.banner-art, .glance-art, .hobby-art, .landscape')) return false;
    }
    return true;
  };
  const name = (el) => {
    const bits = [];
    for (let e = el, i = 0; e && e !== document.body && i < 3; e = e.parentElement, i++) {
      const cls = [...e.classList].filter((c) => !/^(active|on|done|open)$/.test(c)).slice(0, 2).join('.');
      bits.unshift(e.tagName.toLowerCase() + (cls ? '.' + cls : ''));
    }
    return bits.join(' > ');
  };
  const text = (el) => (el.innerText || el.getAttribute('aria-label') || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const rect = (r) => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  // Something scrolls it, clips it on purpose, or it's a map / canvas (two-dimensional content, allowed to pan).
  const contained = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX)) return true;
      if (p.matches('.leaflet-container, .excalidraw, canvas')) return true;
    }
    return false;
  };
  // the part of a box its overflow: hidden / scrolling ancestors actually show (a panel's body scrolls under its footer)
  const shown = (el, raw) => {
    let r = { left: raw.left, right: raw.right, top: raw.top, bottom: raw.bottom };
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ps = getComputedStyle(p);
      if (ps.overflowX !== 'visible' || ps.overflowY !== 'visible') {
        const c = p.getBoundingClientRect();
        r = { left: Math.max(r.left, c.left), right: Math.min(r.right, c.right), top: Math.max(r.top, c.top), bottom: Math.min(r.bottom, c.bottom) };
      }
    }
    r.width = r.right - r.left; r.height = r.bottom - r.top;
    return r;
  };
  // in a bar that stays put while the page scrolls under it (the tab bar, the nav bar): not an overlap
  const pinned = (el) => { for (let p = el; p && p !== document.body; p = p.parentElement) { const ps = getComputedStyle(p).position; if (ps === 'fixed' || ps === 'sticky') return !el.closest('aside.drawer'); } return false; };
  const inDialogOrPage = (el) => !el.closest('[aria-hidden="true"]') || el.closest('aside.drawer');
  // A drawer is open: only it counts (the page behind is covered).
  const drawer = document.querySelector('aside.drawer');
  const scope = drawer || document.body;

  // overflow: the page itself
  const sw = document.documentElement.scrollWidth;
  if (sw > W + 1) out.push({ kind: 'overflow', selector: 'page', detail: `page is ${sw}px wide on a ${W}px screen` });
  // overflow: elements past the right edge that nothing contains
  for (const el of scope.querySelectorAll('body *')) {
    if (el.closest('svg') && el.tagName !== 'svg') continue;
    const r = el.getBoundingClientRect();
    if (r.right > W + 2 && r.width > 0 && visible(el) && !contained(el) && getComputedStyle(el).position !== 'fixed') {
      out.push({ kind: 'overflow', selector: name(el), detail: `right edge at ${Math.round(r.right)}px of ${W}`, rect: rect(r) });
    }
  }
  // clipped: text wider than its box, without deliberate "..." truncation
  const textual = scope.querySelectorAll('button, a, h1, h2, h3, label, .pill, .badge, .tag, .chip-filter, .item-title, .item-meta, .step-name, th, td, summary, .home-stat strong, .banner-title, .banner-tagline');
  for (const el of textual) {
    if (!visible(el) || el.closest('.leaflet-container, .bn-container')) continue;
    const s = getComputedStyle(el);
    if (s.textOverflow === 'ellipsis' || el.querySelector('*[style*="ellipsis"]')) continue;
    if (s.webkitLineClamp && s.webkitLineClamp !== 'none') continue;
    const over = el.scrollWidth - el.clientWidth;
    if (el.clientWidth > 0 && over > 2 && !/(auto|scroll)/.test(s.overflowX)) {
      // a child that ellipsises on purpose makes the parent "wider" harmlessly
      if ([...el.querySelectorAll('*')].some((c) => getComputedStyle(c).textOverflow === 'ellipsis')) continue;
      out.push({ kind: 'clipped', selector: name(el), detail: `"${text(el)}" needs ${el.scrollWidth}px, has ${el.clientWidth}px`, rect: rect(el.getBoundingClientRect()) });
    }
  }
  // overlap: interactive elements on top of each other
  const hits = [...scope.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button]')]
    .filter((el) => visible(el) && inDialogOrPage(el) && getComputedStyle(el).pointerEvents !== 'none' && !el.closest('.leaflet-container, .bn-container, .excalidraw'));
  const boxes = hits.map((el) => [el, shown(el, el.getBoundingClientRect())]).filter(([, r]) => r.width > 1 && r.height > 1);
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const [a, ra] = boxes[i], [b, rb] = boxes[j];
      if (a.contains(b) || b.contains(a) || pinned(a) !== pinned(b)) continue;
      const x = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const y = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (x > 3 && y > 3) {
        // the top one at the overlap's centre wins the click; report only if the other is really covered
        const cx = Math.max(ra.left, rb.left) + x / 2, cy = Math.max(ra.top, rb.top) + y / 2;
        const top = document.elementFromPoint(cx, cy);
        if (!top || !(a.contains(top) || b.contains(top))) continue;
        out.push({ kind: 'overlap', selector: `${name(a)}  ~  ${name(b)}`, detail: `"${text(a)}" and "${text(b)}" overlap ${Math.round(x)}x${Math.round(y)}px`, rect: rect(ra) });
      }
    }
  }
  // overlap: text on text (each element's own text, measured with a range)
  const pieces = [];
  const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT, { acceptNode: (n) => n.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  while (walker.nextNode()) {
    const n = walker.currentNode, el = n.parentElement;
    if (!el || !visible(el) || el.closest('svg, .leaflet-container, .bn-container, .excalidraw, script, style, .visually-hidden')) continue;
    if (el.closest('.stars')) continue;                    // half stars: two layers of stars on purpose
    const range = document.createRange(); range.selectNodeContents(n);
    for (const raw of range.getClientRects()) {
      let r = { left: raw.left, right: raw.right, top: raw.top, bottom: raw.bottom };
      for (let p = el; p && p !== document.body; p = p.parentElement) {   // what overflow: hidden / clip lets show
        const ps = getComputedStyle(p);
        if (ps.overflowX !== 'visible' || ps.overflowY !== 'visible') {
          const c = p.getBoundingClientRect();
          r = { left: Math.max(r.left, c.left), right: Math.min(r.right, c.right), top: Math.max(r.top, c.top), bottom: Math.min(r.bottom, c.bottom) };
        }
      }
      r.width = r.right - r.left; r.height = r.bottom - r.top;
      if (r.width > 2 && r.height > 2 && !pinned(el)) pieces.push([el, r, n.textContent.trim().slice(0, 30)]);
    }
  }
  for (let i = 0; i < pieces.length && i < 1500; i++) {
    for (let j = i + 1; j < pieces.length && j < 1500; j++) {
      const [a, ra, ta] = pieces[i], [b, rb, tb] = pieces[j];
      if (a === b) continue;
      const x = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const y = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (x > 2 && y > Math.min(ra.height, rb.height) * 0.35) {
        out.push({ kind: 'overlap', selector: `${name(a)}  ~  ${name(b)}`, detail: `text "${ta}" over "${tb}"`, rect: rect(ra) });
      }
    }
  }
  // small: touch targets on touch screens
  if (matchMedia('(pointer: coarse)').matches) {
    for (const [el, seen] of boxes) {
      const r = el.getBoundingClientRect();                                        // its real size, not the part scrolled into view
      if (seen.width * seen.height < r.width * r.height * 0.5) continue;           // mostly scrolled out of its row / panel
      if (el.closest('p, li.inline, .hint, .item-meta, .chart-plot, .leaflet-container') && (el.tagName === 'A' || el.matches('.inline'))) continue;   // inline in text
      if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) continue;                       // the label is the target
      if (el.matches('input') && el.closest('label.search-box')) continue;                                                  // (the whole box is)
      if (r.width < 24 || r.height < 24) out.push({ kind: 'small', selector: name(el), detail: `"${text(el)}" is ${Math.round(r.width)}x${Math.round(r.height)}px`, rect: rect(r) });
    }
  }
  // art: in a drawn banner (components/Landscape.jsx) every tree stands on its hill - its base just inside the hill's
  // shape - not floating in the sky or the sea. (The banner is decoration hidden from screen readers, so nothing
  // above looks inside it; this is what does.)
  for (const svg of document.querySelectorAll('svg.landscape')) {
    if (!svg.getBoundingClientRect().width) continue;
    let floating = 0, trees = 0;
    for (const group of svg.querySelectorAll('path.pines')) {
      const hill = svg.querySelector(`path.ridge[data-ridge="${group.dataset.ridge}"]`);
      for (const tree of (group.getAttribute('d') || '').split('M').filter((s) => s.trim())) {
        const nums = tree.match(/-?[0-9.]+/g).map(Number);
        const pts = []; for (let i = 0; i + 1 < nums.length; i += 2) pts.push([nums[i], nums[i + 1]]);
        const baseY = Math.max(...pts.map((q) => q[1]));
        const base = pts.filter((q) => q[1] === baseY);
        const x = base.reduce((s, q) => s + q[0], 0) / base.length;
        trees++;
        const spot = svg.createSVGPoint(); spot.x = x; spot.y = baseY + 3;      // (this Chromium wants an SVGPoint)
        if (!hill || !hill.isPointInFill(spot)) floating++;
      }
    }
    if (floating) out.push({ kind: 'art', selector: name(svg.parentElement) + ' > svg.landscape', detail: `${floating} of ${trees} trees aren't standing on their hill`, rect: rect(svg.getBoundingClientRect()) });
  }
  // image: broken
  for (const img of scope.querySelectorAll('img')) {
    if (img.complete && img.naturalWidth === 0 && visible(img) && img.getAttribute('src') && !img.src.includes('/stand-in/')) out.push({ kind: 'image', selector: name(img), detail: img.getAttribute('src').slice(0, 80), rect: rect(img.getBoundingClientRect()) });
  }
  return out;
}
"""

AXE_RUN = """async () => {
  const scope = document.querySelector('aside.drawer') || document;
  const r = await axe.run(scope, { resultTypes: ['violations'], runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } });
  return r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').flatMap((v) =>
    v.nodes.slice(0, 6).map((n) => {
      // Contrast in the clear nav bar over the banner: named by where it is, not by axe's selector (which changes with
      // whatever else is on the page - "input", "label > input", ".search-box > input"...).
      const el = n.target.length === 1 ? document.querySelector(n.target[0]) : null;
      const overBanner = v.id === 'color-contrast' && el?.closest('.navbar.over-banner:not(.scrolled)');
      return { kind: 'a11y', selector: v.id + ': ' + (overBanner ? 'nav bar over the banner' : n.target.join(' ')),
        detail: (n.failureSummary || v.help).replace(/\\s+/g, ' ').slice(0, 160) };
    }));
}"""

MARK = """(rects) => { for (const [x, y, w, h] of rects) { const d = document.createElement('div'); d.className = 'audit-mark';
  Object.assign(d.style, { position: 'fixed', left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px', outline: '2px solid red', zIndex: 99999, pointerEvents: 'none' });
  document.body.append(d) } }"""


def signed_in_context(browser, **kw):
    """A browser context signed in with this copy's password (run_e2e.ps1 sets E2E_PASSWORD): a session of its own."""
    token = os.environ.get("E2E_TOKEN")               # (an existing session instead - looking at a copy without its password)
    ctx = browser.new_context(ignore_https_errors=True, **kw)
    if token:
        ctx.add_cookies([{"name": "otc_session", "value": token, "url": BASE, "secure": True, "httpOnly": True, "sameSite": "Strict"}])
        return ctx
    ctx.close()
    tls = ssl.create_default_context()
    tls.check_hostname, tls.verify_mode = False, ssl.CERT_NONE
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls), urllib.request.HTTPCookieProcessor(jar))
    opener.open(urllib.request.Request(f"{BASE}/api/auth/login", data=json.dumps({"password": os.environ["E2E_PASSWORD"]}).encode(),
                                       headers={"Content-Type": "application/json"}))
    token = next(c.value for c in jar if c.name == "otc_session")
    ctx = browser.new_context(ignore_https_errors=True, **kw)
    ctx.add_cookies([{"name": "otc_session", "value": token, "url": BASE, "secure": True, "httpOnly": True, "sameSite": "Strict"}])
    return ctx


def routes(page):
    """Every page: the sidebar's (on a wide screen), then each hobby's tabs, then a goal and a journal page."""
    page.goto(BASE)
    page.wait_for_selector(".sidebar a")
    found = []
    for href in page.eval_on_selector_all(".sidebar a[href]", "els => els.map(e => e.getAttribute('href'))"):
        if href not in found:
            found.append(href)
    for href in list(found):
        if href.count("/") == 1 and href not in ("/",):
            page.goto(BASE + href)
            page.wait_for_load_state("networkidle")
            for tab in page.eval_on_selector_all(".section-tabs a[href]", "els => els.map(e => e.getAttribute('href'))"):
                if tab not in found:
                    found.append(tab)
    for listing, link in (("/goals", "a[href^='/goals/']"), ("/journal", "a[href^='/journal/']")):
        page.goto(BASE + listing)
        page.wait_for_load_state("networkidle")
        first = page.eval_on_selector_all(link, "els => els.map(e => e.getAttribute('href'))")
        if first:
            found.append(first[0])
    # a hobby's bare address just redirects to its first tab
    return [r for r in found if not re.fullmatch(r"/[a-z]+", r) or r in ("/goals", "/journal", "/calendar", "/supplies", "/wishlist", "/hobbies")]


def settle(page):
    page.wait_for_load_state("networkidle")
    page.evaluate("document.getAnimations().forEach(a => a.finish())")
    page.wait_for_timeout(250)


def audit(page, where, problems, label, with_axe):
    found = page.evaluate(CHECKS)
    if with_axe:
        if not page.evaluate("typeof axe !== 'undefined'"):
            page.add_script_tag(path=AXE)
        found += page.evaluate(AXE_RUN)
    fresh = []
    for p in found:
        key = f"{p['kind']}|{re.sub(r'[0-9]+', '#', p['selector'])}"
        if key in ACCEPTED:
            continue
        p.update(where=where, key=key)
        problems.append(p)
        fresh.append(p)
    if fresh:
        marks = [p["rect"] for p in fresh if p.get("rect")]
        page.evaluate(MARK, marks)
        safe = re.sub(r"\W+", "_", label)[:90]
        page.screenshot(path=f"{OUT}/audit_{safe}.png", full_page=False)
        page.evaluate("document.querySelectorAll('.audit-mark').forEach(m => m.remove())")
    return len(fresh)


def worker(size_name):
    """One screen size, both themes: its pages and panels. Writes /out/ui_audit_<size>.json."""
    size, w, h, touch = next(s for s in SIZES if s[0] == size_name)
    pages = json.load(open(f"{OUT}/ui_routes.json"))
    problems, console = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in THEMES:
            ctx = signed_in_context(browser, viewport={"width": w, "height": h}, is_mobile=touch and w < 700, has_touch=touch,
                                    device_scale_factor=1, bypass_csp=True, timezone_id="Australia/Brisbane")
            ctx.add_init_script(f"localStorage.setItem('offtheclock.theme', '{theme}')")
            page = ctx.new_page()
            where = {"path": ""}
            tag = f"{size}/{theme}"
            page.on("console", lambda m, wh=where, tg=tag: m.type == "error" and console.append(f"{tg} {wh['path']}: {m.text[:200]}"))
            page.on("pageerror", lambda e, wh=where, tg=tag: console.append(f"{tg} {wh['path']}: page error {e}"))
            page.on("response", lambda r, wh=where, tg=tag: r.status >= 400 and console.append(f"{tg} {wh['path']}: HTTP {r.status} {r.url}"))
            with_axe = size in AXE_SIZES
            # the sign-in screen (a device that isn't signed in): it's a page too
            stranger = browser.new_context(viewport={"width": w, "height": h}, is_mobile=touch and w < 700, has_touch=touch,
                                           device_scale_factor=1, bypass_csp=True, ignore_https_errors=True)
            stranger.add_init_script(f"localStorage.setItem('offtheclock.theme', '{theme}')")
            door = stranger.new_page()
            door.goto(BASE)
            door.get_by_role("heading", name="Welcome back").wait_for(timeout=15000)
            settle(door)
            audit(door, f"{tag} (sign-in)", problems, f"{size}_{theme}_signin", with_axe)
            stranger.close()
            for path in pages:
                where["path"] = path
                page.goto(BASE + path)
                settle(page)
                audit(page, f"{tag} {path}", problems, f"{size}_{theme}_{path}", with_axe)
                banner = page.locator(".page-banner").first
                if theme == "dark" and size in ("pc", "phone") and banner.count():      # the banner gallery, to look over
                    banner.screenshot(path=f"{OUT}/banner_{size}_{re.sub(r'[^a-z]+', '_', path.strip('/')) or 'home'}.png")
            for path, opener in PANELS:
                if not path.startswith(ONLY):
                    continue
                where["path"] = path + " (panel)"
                page.goto(BASE + path)
                settle(page)
                target = page.locator(opener).first
                if not target.count() or not target.is_visible():
                    continue
                target.click()
                try:
                    page.locator("aside.drawer").wait_for(timeout=4000)
                except Exception:
                    continue
                settle(page)
                audit(page, f"{tag} {path} (panel)", problems, f"{size}_{theme}_{path}_panel", with_axe)
                page.keyboard.press("Escape")
            ctx.close()
        browser.close()
    with open(f"{OUT}/ui_audit_{size}.json", "w") as f:
        json.dump({"problems": problems, "console": console}, f)


# The art check, checked: a tiny banner with one tree on its hill and one floating above it. If the detector doesn't
# flag exactly the floating one, the audit stops - a check that silently finds nothing is worse than none.
SELF_TEST = """<div class="banner-art"><svg class="landscape" viewBox="0 0 400 200" width="400" height="200">
  <path class="ridge" data-ridge="0" d="M0 200 L0 120 L400 120 L400 200 Z" />
  <path class="pines" data-ridge="0" d="M100 84 L92 124 L108 124 Z " />
  <path class="pines" data-ridge="1" d="M300 20 L292 60 L308 60 Z " />
  <path class="ridge" data-ridge="1" d="M0 200 L0 150 L400 150 L400 200 Z" />
</svg></div>"""


def self_test(browser):
    page = browser.new_page()
    page.set_content(SELF_TEST)
    found = [p for p in page.evaluate(CHECKS) if p["kind"] == "art"]
    page.close()
    if len(found) != 1 or "1 of 2 trees" not in found[0]["detail"]:
        raise SystemExit(f"The audit's art check is broken (expected one floating tree, got {found}).")


def main():
    """Find the pages once, then one worker process per screen size, side by side; then the report."""
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        self_test(browser)
        ctx = signed_in_context(browser, viewport={"width": 1440, "height": 900}, bypass_csp=True)
        pages = [r for r in routes(ctx.new_page()) if r.startswith(ONLY)]
        browser.close()
    with open(f"{OUT}/ui_routes.json", "w") as f:
        json.dump(pages, f)
    print(f"{len(pages)} pages + {len(PANELS)} panels, at {len(SIZES)} sizes x {len(THEMES)} themes (axe at {', '.join(AXE_SIZES)})", flush=True)
    procs = [subprocess.Popen([sys.executable, __file__, "--worker", s[0]] + ([ONLY] if ONLY else [])) for s in SIZES]
    codes = [proc.wait() for proc in procs]
    problems, console = [], []
    for (size, *_), code in zip(SIZES, codes):
        try:
            part = json.load(open(f"{OUT}/ui_audit_{size}.json"))
        except FileNotFoundError:
            console.append(f"{size}: the audit itself failed (exit {code})")
            continue
        problems += part["problems"]
        console += part["console"]

    # The report: each distinct problem once, with where it shows.
    by_key = {}
    for p in problems:
        entry = by_key.setdefault(p["key"], {"kind": p["kind"], "selector": p["selector"], "detail": p["detail"], "where": []})
        if len(entry["where"]) < 12:
            entry["where"].append(p["where"])
    report = {"problems": list(by_key.values()), "console": sorted(set(console))[:200]}
    with open(f"{OUT}/ui_audit.json", "w") as f:
        json.dump(report, f, indent=1)
    kinds = {}
    for e in by_key.values():
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"\nUI audit: {len(by_key)} distinct problems ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'none'}), "
          f"{len(report['console'])} console / HTTP errors, in {time.time() - started:.0f}s")
    for e in sorted(by_key.values(), key=lambda e: (e["kind"], e["selector"])):
        print(f"  [{e['kind']}] {e['selector']}\n      {e['detail']}\n      at {', '.join(e['where'][:4])}{' ...' if len(e['where']) > 4 else ''}")
    for c in report["console"][:40]:
        print(f"  [console] {c}")
    return 1 if by_key or report["console"] else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        ONLY = sys.argv[3] if len(sys.argv) > 3 else ""
        worker(sys.argv[2])
    else:
        sys.exit(main())
