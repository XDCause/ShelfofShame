"""End-to-end walk-through of Shelf of Shame in a real (headless) browser.

Run it with .\\run_e2e.ps1 (backs up first and restores afterwards - this script changes data).
Runs inside the Playwright container on the app's Docker network, against http://web.
Prints a PASS/FAIL line per step, all browser errors, and saves screenshots to /out.
Written against the user's real data (the Zero and P-40E models, XF-1 etc.); item counts are
read from the API at the start, so adding or removing supplies doesn't break it.
"""
import base64
import json
import re
import time
import traceback
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = "http://web"
OUT = "/out"
results, errors = [], []

# How many supplies there are right now (and how many are Paint), for the list checks.
_supplies = json.load(urllib.request.urlopen(f"{BASE}/api/supplies"))
TOTAL = len(_supplies)
PAINTS = sum(s["category"] == "Paint" for s in _supplies)
MODELS = len(json.load(urllib.request.urlopen(f"{BASE}/api/models")))


def step(name):
    def wrap(fn):
        def run(page, *a):
            t = time.time()
            try:
                fn(page, *a)
                results.append((name, "PASS", f"{time.time() - t:.1f}s"))
            except Exception as e:  # keep going: one broken step shouldn't hide the rest
                results.append((name, "FAIL", f"{type(e).__name__}: {str(e).splitlines()[0][:220]}"))
                safe = re.sub(r"\W+", "_", name)
                try:
                    page.screenshot(path=f"{OUT}/FAIL_{safe}.png", full_page=True)
                except Exception:
                    pass
                page.keyboard.press("Escape")
        return run
    return wrap


def shot(page, name, full=True):
    page.screenshot(path=f"{OUT}/{name}.png", full_page=full)


def drawer(page):
    return page.locator("aside.drawer")


def watch(page, label):
    page.on("console", lambda m: m.type == "error" and errors.append(f"[{label}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{label}] page error: {e}"))
    page.on("response", lambda r: r.status >= 500 and errors.append(f"[{label}] HTTP {r.status} {r.url}"))


# ---------------------------------------------------------------- desktop
@step("Inventory loads with every item")
def inventory_loads(page):
    page.goto(BASE)
    expect(page.locator("tr.row").first).to_be_visible(timeout=15000)
    expect(page.locator("p.summary")).to_contain_text(f"{TOTAL} items")
    assert page.locator("tr.row").count() == TOTAL
    shot(page, "d01_inventory")


@step("Search narrows the list and the total follows")
def search(page):
    page.get_by_label("Search").fill("flat")
    expect(page.locator("p.summary")).to_contain_text(f"of {TOTAL} items", timeout=5000)
    n = page.locator("tr.row").count()
    assert 0 < n < TOTAL, n
    shot(page, "d02_search_flat", full=False)
    page.get_by_label("Search").fill("")
    expect(page.locator("tr.row")).to_have_count(TOTAL)


@step("Category chip filters, tapping again clears")
def chip(page):
    paint = page.get_by_role("button", name=re.compile(r"^Paint \d+$"))
    paint.click()
    expect(page.locator("p.summary")).to_contain_text(f"of {TOTAL} items")
    n = page.locator("tr.row").count()
    assert n == PAINTS, n
    paint.click()
    expect(page.locator("tr.row")).to_have_count(TOTAL)


@step("Groups: close one, close all, remembered after a reload, search opens them")
def groups(page):
    expect(page.get_by_label("Group by")).to_have_value("category")
    paint = page.locator("details.inv-group", has=page.locator("summary", has_text=re.compile(r"^Paint")))
    expect(paint.locator("summary")).to_contain_text(f"{PAINTS} ·")
    paint.locator("summary").click()
    expect(paint.locator("tr.row").first).to_be_hidden()
    expect(page.locator("tr.row:visible")).to_have_count(TOTAL - PAINTS)
    page.get_by_role("button", name="Close all").click()
    expect(page.locator("tr.row:visible")).to_have_count(0)
    shot(page, "d02b_groups_closed", full=False)
    page.reload()
    expect(page.locator("details.inv-group").first).to_be_visible(timeout=15000)
    expect(page.locator("tr.row:visible")).to_have_count(0)      # remembered
    page.get_by_label("Search").fill("XF1 Flat Black")
    expect(page.locator("tr.row:visible", has_text="Acrylic XF1 Flat Black")).to_be_visible()
    page.get_by_label("Search").fill("")
    expect(page.locator("tr.row:visible")).to_have_count(0)      # closed again after the search
    page.get_by_role("button", name="Open all").click()
    expect(page.locator("tr.row:visible")).to_have_count(TOTAL)


@step("Item panel opens; condition Nearly empty makes it Low")
def condition_low(page):
    page.locator("tr.row", has_text="Acrylic XF1 Flat Black").click()
    d = drawer(page)
    expect(d).to_be_visible()
    shot(page, "d03_item_panel")
    d.locator(".condition-picker button", has_text="Nearly empty").click()
    expect(d.locator(".save-flash")).to_contain_text("added to your wishlist")  # automatic
    expect(d).to_contain_text("shows as Low")
    expect(d.locator(".wish-action")).to_contain_text("On wishlist")
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name=re.compile("Needs attention"))).to_be_visible()
    row = page.locator("tr.row", has_text="Acrylic XF1 Flat Black")
    expect(row.locator("td.hide-xs .badge.low")).to_be_visible()
    expect(row.locator("td.hide-xs .tag", has_text="On wishlist")).to_be_visible()
    # ...and its wishlist card says why: the bottle you own is nearly empty
    page.get_by_role("tab", name="Wishlist").click()
    card = page.locator("article.wish-card", has_text="XF1 Flat Black")
    expect(card.locator(".badge.low")).to_have_text("You own 1 · Nearly empty")
    shot(page, "d04b_wishlist_nearly_empty", full=False)
    page.get_by_role("tab", name="Inventory").click()
    shot(page, "d04_needs_attention", full=False)


@step("Panel +/- and stock history")
def plus_minus(page):
    page.locator("tr.row", has_text="Acrylic XF1 Flat Black").click()
    d = drawer(page)
    d.get_by_role("button", name=re.compile("^Add one")).click()
    expect(d.locator(".stock-count strong")).to_have_text("2")
    expect(d.locator(".history li").first).to_contain_text("bought")
    d.get_by_role("button", name="Use one").click()
    expect(d.locator(".stock-count strong")).to_have_text("1")
    expect(d.locator(".history li").first).to_contain_text("used")


@step("Notes save when leaving the field")
def notes(page):
    d = drawer(page)
    d.get_by_placeholder("Anything worth remembering").fill("e2e note")
    d.locator(".item-name").click()  # move focus away
    expect(d.locator(".save-flash")).to_contain_text("Saved")
    d.locator(".condition-picker button", has_text="Sealed").click()
    page.keyboard.press("Escape")


@step("Edit details saves")
def edit_details(page):
    page.locator("tr.row", has_text="Acrylic XF1 Flat Black").click()
    d = drawer(page)
    d.get_by_role("button", name="Edit details").click()
    d.get_by_label("Size").fill("10 ml")
    page.get_by_role("button", name="Save details").click()
    expect(d).to_contain_text("10 ml")
    page.keyboard.press("Escape")


@step("Settings opens from the gear; every section is closed until tapped")
def settings(page):
    page.get_by_role("button", name="Settings").click()
    expect(drawer(page)).to_contain_text("Brands")
    # every section is a closed drop-down: Brands opens when tapped
    brands = drawer(page).locator("details.lookup", has_text="Brands")
    expect(brands.get_by_role("button", name="Remove Hasegawa")).to_be_hidden()
    brands.locator("summary").click()
    expect(brands.get_by_role("button", name="Remove Hasegawa")).to_be_visible()
    shot(page, "d05_manage_lists")
    # Spending is closed until you open it
    spend = drawer(page).locator("details.fold", has_text="Spending")
    expect(spend.locator(".stat-grid")).to_have_count(0)
    spend.locator("summary").click()
    expect(spend.locator(".stat-grid")).to_contain_text("All time")
    expect(spend).to_contain_text("starting stock")
    shot(page, "d05b_spending", full=False)
    page.keyboard.press("Escape")


@step("Add panel: Tamiya code lookup fills the form")
def add_lookup(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    d = drawer(page)
    d.get_by_placeholder("e.g. XF-76 or 81776").fill("XF-2")
    d.get_by_role("button", name="Look up").click()
    expect(d.get_by_label("Name / colour")).to_have_value(re.compile("XF-?2"), timeout=45000)
    shot(page, "d06_add_panel_filled")


@step("Add panel: Add to wishlist")
def add_to_wishlist(page):
    # inside the panel: the page behind can have a "Needs attention -> Add to wishlist" chip too
    drawer(page).get_by_role("button", name="Add to wishlist").click()
    expect(page.locator("p.alert", has_text="added to your wishlist")).to_be_visible()


@step("Wishlist: tick, then move ticked into inventory")
def wishlist_buy(page):
    page.get_by_role("tab", name="Wishlist").click()
    card = page.locator("article.wish-card", has_text="XF2")
    expect(card).to_be_visible()
    shot(page, "d07_wishlist")
    card.locator(".wish-photo").click()
    bar = page.locator(".buy-bar")
    expect(bar).to_be_visible()
    bar.get_by_label("Bought from").fill("E2E shop")
    bar.get_by_role("button", name="Add to inventory").click()
    bar.get_by_role("button", name=re.compile("Yes, add 1")).click()
    expect(page.locator("p.alert", has_text="Added to inventory")).to_be_visible()


@step("Bought item is in inventory with today's date; delete it")
def delete_bought(page):
    page.get_by_role("tab", name="Inventory").click()
    page.locator("tr.row", has_text="XF2 Flat White").click()
    d = drawer(page)
    expect(d.get_by_label("Last bought from")).to_have_value("E2E shop")
    d.get_by_role("button", name="Remove", exact=True).click()
    page.get_by_role("button", name="Yes, remove").click()
    expect(page.locator("tr.row", has_text="XF2 Flat White")).to_have_count(0)


@step("Scan by typed barcode: owned paint opens its panel")
def scan_owned(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    drawer(page).get_by_role("button", name="Type a barcode").click()
    page.get_by_label("Barcode number").fill("4950344070053")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page).locator(".item-name")).to_contain_text("XF76", timeout=20000)  # its item panel
    page.keyboard.press("Escape")


@step("Scan by typed barcode: unknown opens Add panel")
def scan_unknown(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    drawer(page).get_by_role("button", name="Type a barcode").click()
    page.get_by_label("Barcode number").fill("036000291452")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page)).to_contain_text("New barcode", timeout=20000)
    shot(page, "d08_scan_unknown")
    page.keyboard.press("Escape")


@step("Models: shelf of shame, list and the Zero's checklist")
def models(page):
    page.get_by_role("tab", name="Models").click()
    expect(page.locator(".model-card")).to_have_count(MODELS)
    expect(page.locator(".stat-grid")).to_contain_text("Shelf of shame")
    shot(page, "d09_models")
    page.locator(".model-card", has_text="Zero").click()
    d = drawer(page)
    expect(d).to_contain_text("9/9")
    shot(page, "d10_model_zero")
    page.keyboard.press("Escape")


@step("Models: paste a list into the P-40E, then missing to wishlist")
def model_paste(page):
    page.locator(".model-card", has_text="P-40E").click()
    d = drawer(page)
    d.get_by_role("button", name="Paste a list").click()
    d.locator(".paste-list textarea").fill("XF-1 Flat Black\tTyres\nXF-2 Flat White - Stars\nOld silver tin")
    d.get_by_role("button", name="Add paints").click()
    expect(d.locator(".checklist li")).to_have_count(3)
    shot(page, "d11_model_p40_pasted")
    d.get_by_role("button", name=re.compile("missing to wishlist")).click()
    expect(d.locator(".save-flash")).to_contain_text("Added to wishlist")
    d.get_by_label("Have Old silver tin").check()
    expect(d).to_contain_text("2/3")
    page.keyboard.press("Escape")


@step("Add model: Hasegawa lookup by series code")
def add_model_hasegawa(page):
    page.get_by_role("button", name="+ Add model").click()
    d = drawer(page)
    d.get_by_role("button", name="Hasegawa", exact=True).click()
    d.get_by_placeholder("e.g. JT86 or 09086").fill("PT29")
    d.get_by_role("button", name="Look up").click()
    expect(d.get_by_label("Model name")).to_have_value(re.compile("F-2B"), timeout=45000)
    shot(page, "d12_add_model_hasegawa")
    page.keyboard.press("Escape")


@step("Undo after + in the list puts it back (and is in the history)")
def undo(page):
    page.get_by_role("tab", name="Inventory").click()
    row = page.locator("tr.row", has_text="Acrylic XF1 Flat Black")
    row.get_by_role("button", name=re.compile("^Add one")).click()
    expect(row.locator(".qty span")).to_have_text("2")
    toast = page.locator(".toast")
    expect(toast).to_contain_text("Added one: Acrylic XF1 Flat Black")
    toast.get_by_role("button", name="Undo").click()
    expect(row.locator(".qty span")).to_have_text("1")
    row.click()
    expect(drawer(page).locator(".history li").first).to_contain_text("undo")
    page.keyboard.press("Escape")


@step("Item panel: + Add to wishlist button")
def add_to_wishlist_button(page):
    page.get_by_role("tab", name="Inventory").click()
    page.locator("tr.row", has_text="Acrylic XF7 Flat Red").click()
    d = drawer(page)
    d.get_by_role("button", name="+ Add to wishlist").click()
    expect(d.locator(".wish-action")).to_contain_text("On wishlist")
    page.keyboard.press("Escape")
    page.get_by_role("tab", name="Wishlist").click()
    expect(page.locator("article.wish-card", has_text="XF7 Flat Red")).to_be_visible()
    page.get_by_role("tab", name="Inventory").click()


@step("Duplicate check while typing a name")
def duplicate_check(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    d = drawer(page)
    d.get_by_label("Name / colour").fill("Flat Black")
    expect(d.locator(".similar")).to_contain_text("Acrylic XF1 Flat Black")
    shot(page, "d13_duplicate_check")
    page.keyboard.press("Escape")


@step("Wishlist: total line and the side-panel form")
def wishlist_panel(page):
    page.get_by_role("tab", name="Wishlist").click()
    page.locator(".wish-head").get_by_role("button", name="+ Add").click()
    expect(drawer(page).locator(".drawer-head")).to_contain_text("Add to wishlist")
    shot(page, "d14_wishlist_panel")
    page.keyboard.press("Escape")


@step("Shop Tamiya: search the catalogue (search only, no tamiya.com fetch)")
def shop_tamiya(page):
    page.get_by_role("tab", name="Wishlist").click()
    page.get_by_role("button", name="Shop Tamiya").click()
    d = drawer(page)
    d.get_by_label("Search Tamiya").fill("panel line black")
    row = d.locator(".shop-results li", has_text="Panel Line Accent Color (Black)")
    expect(row).to_be_visible()
    # either addable, or already on your real wishlist
    expect(row.get_by_role("button", name="+ Wishlist").or_(row.get_by_text("On wishlist"))).to_be_visible()
    expect(d.locator(".shop-results li")).to_have_count(1)
    shot(page, "d15_shop_tamiya", full=False)
    page.keyboard.press("Escape")


@step("Used the last one, not replacing it: remove from inventory and wishlist")
def used_up(page):
    page.get_by_role("tab", name="Inventory").click()
    row = page.locator("tr.row", has_text="Acrylic XF71 Cockpit Green")
    row.get_by_role("button", name=re.compile("^Use one")).click()
    toast = page.locator(".toast")
    expect(toast).to_contain_text("Used the last one: Acrylic XF71 Cockpit Green")
    toast.get_by_role("button", name="Not replacing?").click()
    d = drawer(page)
    expect(d.locator(".used-up")).to_contain_text("All used up")
    expect(d.locator(".used-up")).to_contain_text("(and your wishlist)")  # running out put it there
    shot(page, "d16_used_up", full=False)
    d.get_by_role("button", name="Remove from inventory").click()
    page.get_by_role("button", name="Yes, remove").click()
    expect(page.locator("p.alert", has_text="removed from your inventory")).to_be_visible()
    expect(page.locator("tr.row", has_text="XF71 Cockpit Green")).to_have_count(0)
    page.get_by_role("tab", name="Wishlist").click()
    expect(page.locator("article.wish-card", has_text="XF71")).to_have_count(0)
    page.get_by_role("tab", name="Inventory").click()


@step("Model: Search Scalemates link")
def scalemates(page):
    page.get_by_role("tab", name="Models").click()
    page.locator(".model-card", has_text="Zero").click()
    link = drawer(page).get_by_role("link", name=re.compile("Search Scalemates"))
    expect(link).to_have_attribute("href", re.compile(r"scalemates\.com/search\.php\?q=Tamiya"))
    page.keyboard.press("Escape")


@step("Desktop: page tabs in the nav bar, no bottom tab bar")
def desktop_tabs(page):
    expect(page.get_by_role("tab", name="Colours")).to_be_visible()
    expect(page.locator(".tabbar")).to_be_hidden()
    expect(page.get_by_role("button", name="Scan a barcode")).to_be_visible()


@step("Model Edit details opens, saves and stays saved")
def model_edit(page):
    page.locator(".model-card", has_text="P-40E").click()
    d = drawer(page)
    d.get_by_role("button", name="Edit details").click()
    expect(d.get_by_label("Scale", exact=True)).to_be_visible()
    d.get_by_label("Scale", exact=True).fill("1:48")
    page.get_by_role("button", name="Save details").click()
    expect(d).to_contain_text("1:48 · Hasegawa")
    page.keyboard.press("Escape")


@step("Settings lists: brand used only by a model can't be removed")
def lists_protect(page):
    page.get_by_role("button", name="Settings").click()
    drawer(page).locator("details.lookup", has_text="Brands").locator("summary").click()
    expect(drawer(page).get_by_role("button", name="Remove Hasegawa")).to_be_disabled()
    page.keyboard.press("Escape")


@step("Escape closes panels; no panel left open")
def no_panel(page):
    expect(page.locator("aside.drawer")).to_have_count(0)


# ---------------------------------------------------------------- new in the kit-stash update
# A 1x1 PNG for the build-log photo.
PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def open_model(page, name):
    page.get_by_role("tab", name="Models").click()
    page.locator(".model-card", has_text=name).click()
    return drawer(page)


@step("Kit paints: pick more from the Sherman's Tamiya list (cached, no fetch)")
def kit_paints(page):
    d = open_model(page, "Sherman")
    expect(d.locator(".checklist li").first).to_be_visible()   # loaded before counting
    before = d.locator(".checklist li").count()
    d.get_by_role("button", name="Pick from Tamiya's paint list for this kit").click()
    picker = page.locator("aside.drawer").last
    expect(picker.locator(".section-title", has_text="Lacquer paints (LP)")).to_be_visible(timeout=20000)
    expect(picker.locator("li", has_text="Acrylic XF62 Olive Drab")).to_contain_text("On the list")
    picker.locator("li", has_text="Panel Line Accent Color (Black)").get_by_role("checkbox").check()
    shot(page, "d17_kit_paints_picker", full=False)
    picker.get_by_role("button", name="Add 1 paint").click()
    expect(d.locator(".checklist li")).to_have_count(before + 1)
    expect(d.locator(".save-flash")).to_contain_text("from the kit's list")
    page.keyboard.press("Escape")


@step("Timer: start shows the banner and starts the build, stop saves the time")
def timer(page):
    d = open_model(page, "Sherman")
    d.get_by_role("button", name="Start timer").click()
    expect(d.locator(".timer.running")).to_be_visible()
    expect(d.locator(".status-picker [aria-pressed='true']")).to_have_text("In progress")
    page.keyboard.press("Escape")
    expect(page.locator(".timer-banner")).to_contain_text("Sherman")
    page.locator(".timer-banner").click()
    d = drawer(page)
    d.get_by_label("What did you do").fill("Lower hull")
    d.get_by_role("button", name="Stop").click()
    expect(d.locator(".save-flash")).to_contain_text("Time saved")
    d.get_by_role("button", name="+ Add time by hand").click()
    d.get_by_label("Hours").fill("1")
    d.get_by_label("Minutes").fill("30")
    d.get_by_role("button", name="Add time").click()
    expect(d.locator(".panel-section", has_text="Start timer")).to_contain_text("1 h 30 min")
    page.keyboard.press("Escape")
    expect(page.locator(".timer-banner")).to_have_count(0)


@step("Build log: a note with a photo")
def build_log(page):
    d = open_model(page, "Sherman")
    d.get_by_label("Build log note").fill("Hull assembled, ready for primer")
    d.locator(".log-form input[type=file]").set_input_files(
        {"name": "hull.png", "mimeType": "image/png", "buffer": PIXEL})
    d.get_by_role("button", name="Add to log").click()
    entry = d.locator(".log li").first
    expect(entry).to_contain_text("Hull assembled")
    expect(entry.locator("img")).to_be_visible()
    shot(page, "d18_build_log", full=False)
    page.keyboard.press("Escape")


@step("Kit stash: price paid shows on the model and in the stash value")
def stash(page):
    d = open_model(page, "Sherman")
    d.get_by_role("button", name="Edit details").click()
    d = drawer(page)
    expect(d.get_by_label("Bought from")).to_be_visible()
    d.get_by_label("Price paid ($)").fill("54.95")
    page.get_by_role("button", name="Save details").click()
    expect(drawer(page)).to_contain_text("Paid $54.95")
    page.keyboard.press("Escape")
    expect(page.locator(".stat-grid")).to_contain_text("$54.95")
    page.get_by_role("button", name=re.compile("^Shelf of shame")).click()
    expect(page.locator(".model-card", has_text="Sherman")).to_be_visible()
    shot(page, "d19_models_stash", full=False)


@step("Colours: a new mix, and a mix on a model's paint list")
def mixes(page):
    page.get_by_role("tab", name="Colours").click()
    page.get_by_role("button", name="+ New mix").click()
    page.get_by_label("Recipe").fill("XF-62 + XF-2 (3:1)")
    page.get_by_label("Name (optional)").fill("Faded olive drab")
    page.get_by_role("button", name="Save").click()
    card = page.locator(".card", has_text="Faded olive drab")
    expect(card).to_contain_text("Acrylic XF62 Olive Drab")
    expect(card.locator(".tag", has_text="Need")).to_have_count(2)
    d = open_model(page, "P-40E")
    d.get_by_label("Paint", exact=True).fill("XF-62 + XF-1 (2:1)")
    d.get_by_label("What it's for").fill("Weathered panels")
    d.get_by_role("button", name="Add", exact=True).click()
    row = d.locator(".checklist li", has_text="XF-62 + XF-1 (2:1)")
    expect(row.locator(".tag", has_text="Mix")).to_be_visible()
    expect(row.locator(".mix-parts")).to_contain_text("Acrylic XF1 Flat Black ✓")
    page.keyboard.press("Escape")


@step("Colours: find a match by name, and your own match")
def matches(page):
    page.get_by_role("tab", name="Colours").click()
    page.get_by_label("Find a colour match").fill("XF-62")
    page.locator(".pick-list button", has_text="Acrylic XF62 Olive Drab").click()
    found = page.locator(".find-match .matches")
    expect(found).to_contain_text("Same name")
    expect(found).to_contain_text("LP-28")
    shot(page, "d20_colour_matches", full=False)
    page.get_by_role("button", name="+ New match").click()
    page.get_by_label("Name", exact=True).fill("US Olive Drab")
    page.get_by_label("Paints, one per line").fill("XF-62\nMr. Color C38")
    page.get_by_label("Where the match comes from").fill("Sherman instructions")
    page.get_by_role("button", name="Save").click()
    expect(page.locator(".card", has_text="US Olive Drab")).to_contain_text("Mr. Color C38")


@step("Item panel: used on (models) and colour matches")
def used_on(page):
    page.get_by_role("tab", name="Inventory").click()
    page.locator("tr.row", has_text="Acrylic XF1 Flat Black").click()
    d = drawer(page)
    used = d.locator(".panel-section", has_text="Used on")
    expect(used).to_contain_text("Zero")
    expect(used).to_contain_text("Sherman")
    d.locator("summary", has_text="Colour matches").click()
    expect(d.locator(".matches")).to_contain_text("LP-3 Flat Black")
    shot(page, "d21_used_on", full=False)
    used.get_by_role("button", name=re.compile("Sherman")).click()
    expect(drawer(page).locator(".item-name")).to_contain_text("Sherman")
    page.keyboard.press("Escape")


@step("Gundam: the RX-78-2's grade, build steps and panel line colours")
def gundam(page):
    d = open_model(page, "RX-78-2")
    expect(d.locator(".item-sub").first).to_contain_text("HG · 1/144 · Bandai · G5057403")
    expect(d.locator(".steps button")).to_have_count(4)
    expect(d.locator(".checklist li", has_text="Panel Line Gray")).to_contain_text("In inventory")
    d.locator(".steps button", has_text="Panel lined").click()
    expect(d.locator(".steps button[aria-pressed='true']")).to_have_count(2)   # Built + Panel lined
    expect(d.locator(".status-picker [aria-pressed='true']")).to_have_text("In progress")
    shot(page, "d23_gundam", full=False)
    d.locator(".steps button", has_text="Panel lined").click()                 # untick: back to Built
    expect(d.locator(".steps button[aria-pressed='true']")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(page.locator(".model-card", has_text="RX-78-2")).to_contain_text("Built, step 1 of 4")


@step("Warhammer: a box of 10 with its army, a new brand, minis painted; hobby filter")
def warhammer(page):
    page.get_by_role("tab", name="Models").click()
    page.get_by_role("button", name="+ Add model").click()
    d = drawer(page)
    d.locator(".hobby-picker button", has_text="Warhammer").click()
    expect(d.get_by_label("Brand")).to_have_value("new:Games Workshop")
    d.get_by_label("Model name").fill("Intercessors")
    d.get_by_label("Army").fill("Ultramarines")
    d.get_by_label("Minis in the box").fill("10")
    page.get_by_role("button", name="Add model", exact=True).click()
    d = drawer(page)
    expect(d.locator(".item-sub").first).to_contain_text("Ultramarines · Games Workshop")
    d.get_by_role("button", name="One more painted").click()
    expect(d.locator(".minis")).to_contain_text("1 of 10")
    page.keyboard.press("Escape")
    hobby = page.locator(".hobby-filter")
    expect(hobby).to_contain_text("Gundam")
    hobby.get_by_role("button", name=re.compile("^Warhammer")).click()
    expect(page.locator(".model-card")).to_have_count(1)
    expect(page.locator(".model-card")).to_contain_text("1 of 10 minis painted")
    shot(page, "d24_hobbies", full=False)
    hobby.get_by_role("button", name=re.compile("^All")).click()


@step("Settings: price guide, default shop, backups, exports, catalogue")
def settings_more(page):
    page.get_by_role("button", name="Settings").click()
    d = drawer(page)
    d.locator("summary", has_text="Price guide").click()
    expect(d.locator(".settings > .fold", has_text="Price guide")).to_contain_text("$10.95")
    d.locator("summary", has_text="Default shop").click()
    expect(d.get_by_label("Shop")).to_have_value("Hobbyrama")
    d.locator("summary", has_text="Backups").click()
    expect(d.locator(".settings > .fold", has_text="Backups")).to_contain_text("Last backup")
    expect(d.get_by_role("link", name="Download latest")).to_have_attribute(
        "href", re.compile(r"/api/backups/hobby_inventory_\d{8}_\d{6}\.dump"))
    d.locator("summary", has_text="Export to CSV").click()
    link = d.locator(".settings > .fold", has_text="Export to CSV").get_by_role("link").first
    csv = page.request.get(BASE + link.get_attribute("href"))
    assert csv.ok and csv.headers["content-type"].startswith("text/csv"), csv.status
    d.locator("summary", has_text="Tamiya catalogue").click()
    expect(d.locator(".settings > .fold", has_text="Tamiya catalogue")).to_contain_text("Tamiya products")
    shot(page, "d22_settings", full=False)
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- phone
@step("Phone: tab bar, nav bar, sheets, every page fits the screen")
def phone(page):
    page.goto(BASE)
    expect(page.locator("tr.row").first).to_be_visible(timeout=15000)
    shot(page, "m01_inventory", full=False)
    expect(page.locator(".tabbar")).to_be_visible()             # tabs at the bottom on phones
    expect(page.locator(".navbar .tabs")).to_be_hidden()
    expect(page.get_by_role("button", name="Scan a barcode")).to_be_visible()
    size = page.get_by_label("Search").evaluate("e => getComputedStyle(e).fontSize")
    assert size == "16px", f"search box font {size} (iPhone zooms in below 16px)"
    page.locator("tr.row").first.click()
    expect(drawer(page)).to_be_visible()
    expect(page.locator(".tabbar")).to_be_hidden()              # a sheet covers the tab bar
    page.wait_for_timeout(400)  # let the sheet finish sliding up
    shot(page, "m02_item_panel", full=False)
    page.keyboard.press("Escape")
    for name in ("Wishlist", "Models", "Colours", "Inventory"):
        page.locator(".tabbar button", has_text=name).click()
        expect(page.locator(".tabbar button[aria-current=page]")).to_have_text(name)
        page.wait_for_timeout(300)
        shot(page, f"m_{name.lower()}", full=False)
        width = page.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"{name} is {width}px wide on a 390px phone"
    page.locator(".tabbar button", has_text="Models").click()
    page.locator(".model-card", has_text="Zero").click()
    page.wait_for_timeout(400)
    shot(page, "m06_model_panel", full=False)
    button = page.get_by_role("button", name="Start timer").bounding_box()
    assert button["height"] >= 44, f"Start timer is {button['height']}px tall (44 for a finger)"


with sync_playwright() as p:
    browser = p.chromium.launch()
    desk = browser.new_page(viewport={"width": 1280, "height": 860})
    watch(desk, "desktop")
    for fn in (inventory_loads, search, chip, groups, condition_low, plus_minus, notes, edit_details, settings,
               add_lookup, add_to_wishlist, wishlist_buy, delete_bought, scan_owned, scan_unknown,
               models, model_paste, add_model_hasegawa, undo, add_to_wishlist_button, duplicate_check, wishlist_panel, shop_tamiya, used_up,
               scalemates, desktop_tabs, model_edit, lists_protect, kit_paints, timer, build_log, stash, mixes,
               matches, used_on, gundam, warhammer, settings_more, no_panel):
        fn(desk)
    ctx = browser.new_context(**p.devices["iPhone 13"])
    mob = ctx.new_page()
    watch(mob, "phone")
    phone(mob)
    browser.close()

for name, status, info in results:
    print(f"{status}  {name}  ({info})")
print(f"\n{sum(r[1] == 'PASS' for r in results)}/{len(results)} steps passed")
print("\nBrowser errors:" if errors else "\nBrowser errors: none")
for e in errors:
    print("  " + e)
raise SystemExit(0 if all(r[1] == "PASS" for r in results) and not errors else 1)
