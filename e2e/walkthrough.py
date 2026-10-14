"""End-to-end walk-through of Off the Clock in a real (headless) browser.

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
MARK = f"e2e{int(time.time())}"   # a word only this run's journal page contains


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


def go(page, name):
    """Open a page from the navigation: the sidebar on desktop, the tab bar on phones (only one
    of them is visible, so the link name is enough). A hobby's own pages (Colours) are tabs at
    the top of the hobby, so go to the hobby first."""
    if name in SECTION_TABS:
        go(page, SECTION_TABS[name])
        page.locator(".section-tabs").get_by_role("link", name=name, exact=True).click()
    else:
        page.get_by_role("link", name=name, exact=True).click()


SECTION_TABS = {"Colours": "Models", "Plays": "Board games", "Gear": "Volleyball", "Videos": "Volleyball"}


def watch(page, label):
    page.on("console", lambda m: m.type == "error" and errors.append(f"[{label}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{label}] page error: {e}"))
    page.on("response", lambda r: r.status >= 500 and errors.append(f"[{label}] HTTP {r.status} {r.url}"))


# ---------------------------------------------------------------- desktop
@step("Home: greeting, every hobby's tiles, Coming up, and the numbers open their pages")
def home(page):
    page.goto(BASE)
    expect(page.locator(".hero h2")).to_have_text(re.compile("^Good (morning|afternoon|evening)$"), timeout=15000)
    stats = page.locator(".home-stat")
    expect(stats.filter(has_text="Supplies")).to_contain_text(str(TOTAL))
    for tile in ("Shelf of shame", "Board games", "Volleyball", "Next game"):
        expect(stats.filter(has_text=tile)).to_be_visible()
    expect(stats).to_have_count(10)
    expect(page.locator(".home-card", has_text="Recent activity").locator(".pill").first).to_be_visible()
    expect(page.locator(".home-card", has_text="Coming up")).to_be_visible()
    expect(page.locator(".quick-action")).to_have_count(8)
    shot(page, "d00_home", full=False)
    stats.filter(has_text="To buy").click()
    expect(page).to_have_url(BASE + "/wishlist")
    expect(page.locator(".navbar h1")).to_contain_text("Wishlist")
    page.go_back()
    expect(page).to_have_url(BASE + "/")
    page.goto(BASE + "/no-such-page")                       # unknown addresses get a way home
    expect(page.get_by_role("link", name="Go home")).to_be_visible()


@step("Supplies loads with every item (the old address still works)")
def inventory_loads(page):
    page.goto(BASE + "/models/inventory")                   # where it used to be...
    expect(page).to_have_url(BASE + "/supplies")            # ...moves to the core page
    expect(page.locator(".navbar h1")).to_contain_text("Hobby supplies")
    expect(page.locator("tr.row").first).to_be_visible(timeout=15000)
    expect(page.locator("p.summary")).to_contain_text(f"{TOTAL} items")
    assert page.locator("tr.row").count() == TOTAL
    shot(page, "d01_inventory")


@step("Search narrows the list and the total follows")
def search(page):
    page.get_by_label("Search", exact=True).fill("flat")
    expect(page.locator("p.summary")).to_contain_text(f"of {TOTAL} items", timeout=5000)
    n = page.locator("tr.row").count()
    assert 0 < n < TOTAL, n
    shot(page, "d02_search_flat", full=False)
    page.get_by_label("Search", exact=True).fill("")
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
    page.get_by_label("Search", exact=True).fill("XF1 Flat Black")
    expect(page.locator("tr.row:visible", has_text="Acrylic XF1 Flat Black")).to_be_visible()
    page.get_by_label("Search", exact=True).fill("")
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
    go(page, "Wishlist")
    card = page.locator("article.wish-card", has_text="XF1 Flat Black")
    expect(card.locator(".badge.low")).to_have_text("You own 1 · Nearly empty")
    shot(page, "d04b_wishlist_nearly_empty", full=False)
    go(page, "Supplies")
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
    go(page, "Wishlist")
    card = page.locator("article.wish-card", has_text="XF2")
    expect(card).to_be_visible()
    shot(page, "d07_wishlist")
    card.locator(".wish-photo").click()
    bar = page.locator(".buy-bar")
    expect(bar).to_be_visible()
    bar.get_by_label("Bought from").fill("E2E shop")
    expect(card.get_by_role("button", name="Bought")).to_have_count(0)   # one way to buy: tick, then the bar
    bar.get_by_role("button", name=re.compile(r"^Add \d+ to inventory$")).click()
    notice = page.locator("p.alert", has_text="Added to inventory")
    expect(notice).to_be_visible()
    notice.get_by_role("button", name="Close message").click()          # the green bar has a close button
    expect(notice).to_have_count(0)


@step("Bought item is in inventory with today's date; delete it")
def delete_bought(page):
    go(page, "Supplies")
    page.locator("tr.row", has_text="XF2 Flat White").click()
    d = drawer(page)
    expect(d.get_by_label("Last bought from")).to_have_value("E2E shop")
    d.get_by_role("button", name="Remove", exact=True).click()
    page.get_by_role("button", name="Yes, remove").click()
    expect(page.locator("tr.row", has_text="XF2 Flat White")).to_have_count(0)


@step("Scan by typed barcode: owned paint opens its panel")
def scan_owned(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    drawer(page).get_by_role("button", name="Use barcode").click()       # one button, two ways in
    drawer(page).get_by_role("button", name="Type the number").click()
    page.get_by_label("Barcode number").fill("4950344070053")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page).locator(".item-name")).to_contain_text("XF76", timeout=20000)  # its item panel
    page.keyboard.press("Escape")


@step("Scan by typed barcode: unknown opens Add panel")
def scan_unknown(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    drawer(page).get_by_role("button", name="Use barcode").click()       # one button, two ways in
    drawer(page).get_by_role("button", name="Type the number").click()
    page.get_by_label("Barcode number").fill("036000291452")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page)).to_contain_text("New barcode", timeout=20000)
    shot(page, "d08_scan_unknown")
    page.keyboard.press("Escape")


@step("Models: shelf of shame, list and the Zero's checklist")
def models(page):
    go(page, "Models")
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
    go(page, "Supplies")
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


@step("Item panel: + Add to wishlist, and take it off again")
def add_to_wishlist_button(page):
    go(page, "Supplies")
    page.locator("tr.row", has_text="Acrylic XF7 Flat Red").click()
    d = drawer(page)
    d.get_by_role("button", name="+ Add to wishlist").click()
    expect(d.locator(".wish-action")).to_contain_text("On wishlist")
    d.get_by_role("button", name="On wishlist. Take it off").click()
    expect(d.get_by_role("button", name="+ Add to wishlist")).to_be_visible()
    expect(d.locator(".save-flash")).to_contain_text("Taken off your wishlist")
    d.get_by_role("button", name="+ Add to wishlist").click()
    # Photo options wait behind a drop-down; the barcode stays in view.
    expect(d.get_by_role("button", name=re.compile("barcode"))).to_be_visible()
    expect(d.get_by_role("button", name=re.compile("Upload photo|Replace photo"))).to_be_hidden()
    d.locator("summary", has_text="Photo options").click()
    expect(d.get_by_role("button", name=re.compile("Upload photo|Replace photo"))).to_be_visible()
    page.keyboard.press("Escape")
    go(page, "Wishlist")
    expect(page.locator("article.wish-card", has_text="XF7 Flat Red")).to_be_visible()
    go(page, "Supplies")


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
    go(page, "Wishlist")
    page.locator(".wish-head").get_by_role("button", name="+ Add").click()
    expect(drawer(page).locator(".drawer-head")).to_contain_text("Add to wishlist")
    shot(page, "d14_wishlist_panel")
    page.keyboard.press("Escape")


@step("Wishlist + Add: search Tamiya in the panel (search only, no tamiya.com fetch)")
def shop_tamiya(page):
    go(page, "Wishlist")
    expect(page.locator(".head-buttons button")).to_have_count(1)            # just + Add
    page.locator(".wish-head").get_by_role("button", name="+ Add").click()
    d = drawer(page)
    expect(d.get_by_role("button", name="Use barcode")).to_be_visible()
    d.get_by_label("Search the Tamiya catalogue").fill("panel line black")
    row = d.locator(".shop-results li", has_text="Panel Line Accent Color (Black)")
    expect(row).to_be_visible()
    # either addable, or already on your real wishlist
    expect(row.get_by_role("button", name="+ Wishlist").or_(row.get_by_text("On wishlist"))).to_be_visible()
    expect(d.locator(".shop-results li")).to_have_count(1)
    shot(page, "d15_shop_tamiya", full=False)
    page.keyboard.press("Escape")


@step("Used the last one, not replacing it: remove from inventory and wishlist")
def used_up(page):
    go(page, "Supplies")
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
    go(page, "Wishlist")
    expect(page.locator("article.wish-card", has_text="XF71")).to_have_count(0)
    go(page, "Supplies")


@step("Model: Search Scalemates link")
def scalemates(page):
    go(page, "Models")
    page.locator(".model-card", has_text="Zero").click()
    link = drawer(page).get_by_role("link", name=re.compile("Search Scalemates"))
    expect(link).to_have_attribute("href", re.compile(r"scalemates\.com/search\.php\?q=Tamiya"))
    page.keyboard.press("Escape")


@step("Desktop: sidebar with the core pages and one entry per hobby; a hobby's pages are tabs")
def desktop_tabs(page):
    sidebar = page.locator(".sidebar")
    expect(sidebar).to_contain_text("Off the Clock")
    for name in ("Home", "Journal", "Calendar", "Supplies", "Wishlist", "Models", "Board games", "Volleyball"):
        expect(sidebar.get_by_role("link", name=name, exact=True)).to_be_visible()
    expect(sidebar.get_by_role("link", name="Colours")).to_have_count(0)
    expect(page.locator(".tabbar")).to_be_hidden()
    go(page, "Colours")
    expect(sidebar.locator("a.active")).to_have_text("Models")
    expect(page.locator(".section-tabs a[aria-current=page]")).to_have_text("Colours")
    expect(page).to_have_title(re.compile("Colours · Models"))
    expect(page.get_by_role("button", name="Scan a barcode")).to_be_visible()


@step("Model Edit details opens, saves and stays saved")
def model_edit(page):
    go(page, "Models")
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
    go(page, "Models")
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
    go(page, "Colours")
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
    go(page, "Colours")
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
    go(page, "Supplies")
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
    # In progress, Built: the next step shows as underway
    expect(page.locator(".model-card", has_text="RX-78-2")).to_contain_text("Panel lining · step 2 of 4")
    expect(page.locator(".model-card", has_text="RX-78-2").locator("img")).to_be_visible()  # HLJ box photo


@step("Bandai lookup: the box code fills name, grade and scale (cached - no hlj.com fetch)")
def bandai_lookup(page):
    go(page, "Models")
    page.get_by_role("button", name="+ Add model").click()
    d = drawer(page)
    d.locator(".hobby-picker button", has_text="Gundam").click()
    d.get_by_label("Code from the box, its barcode, or the name").fill("G5057403")
    d.get_by_role("button", name="Look up").click()
    expect(d.get_by_label("Model name")).to_have_value("HGUC Revive RX-78-2 Gundam")
    expect(d.get_by_label("Grade")).to_have_value("HG")
    expect(d.locator(".preview img")).to_be_visible()
    shot(page, "d25_bandai_lookup", full=False)
    page.get_by_role("button", name="Cancel").click()


@step("Warhammer: a box of 10 with its army, a new brand, minis painted; hobby filter")
def warhammer(page):
    go(page, "Models")
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


@step("Journal: today's entry, typing, an @mention, saves by itself and survives a reload")
def journal_write(page):
    page.goto(BASE)
    page.get_by_role("button", name="Write today's entry").click()
    expect(page).to_have_url(re.compile(r"/journal/\d+$"))
    expect(page.get_by_label("Title")).not_to_have_value("")             # today's date as the title
    editor = page.locator(".bn-editor")
    editor.click(timeout=20000)                                          # the editor loads on demand
    page.keyboard.type("Started the hull of the @Sher")
    page.get_by_role("option", name=re.compile("Sherman")).click()
    page.keyboard.type(f"today. Primer next. {MARK}")
    expect(page.locator(".save-status")).to_have_text("Saved", timeout=10000)
    expect(page.locator(".journal-links")).to_contain_text("Sherman")
    page.get_by_label("Add a tag").fill(f"tag{MARK}")
    page.keyboard.press("Enter")
    expect(page.locator(".tag-chip")).to_have_text(re.compile(f"#tag{MARK}"))
    expect(page.locator(".save-status")).to_have_text("Saved", timeout=10000)
    shot(page, "d26_journal_page", full=False)
    page.reload()
    expect(page.locator(".bn-editor")).to_contain_text("Primer next.", timeout=20000)
    expect(page.locator(".bn-editor .mention")).to_contain_text("Sherman")
    expect(page.locator(".tag-chip")).to_have_text(re.compile(f"#tag{MARK}"))


@step("Journal: a mention opens the model, which lists the page; search and tags find it")
def journal_links(page):
    page.locator(".bn-editor .mention").first.click()
    d = drawer(page)
    expect(d.locator(".item-name")).to_contain_text("Sherman")
    section = d.locator(".panel-section", has_text="In the journal")
    expect(section.locator(".page-row", has_text=MARK)).to_have_count(1)
    page.keyboard.press("Escape")
    go(page, "Journal")
    page.get_by_label("Search the journal").fill(f"primer {MARK}")
    expect(page.locator(".journal-card")).to_have_count(1)
    page.get_by_label("Search the journal").fill("volleyball")
    expect(page.locator(".journal-card")).to_have_count(0)
    page.get_by_label("Search the journal").fill("")
    page.get_by_role("button", name=re.compile(f"^#tag{MARK}")).click()
    expect(page.locator(".journal-card")).to_have_count(1)
    shot(page, "d27_journal_list", full=False)


@step("Journal: + Write about it from a model, then delete the page")
def journal_from_model(page):
    go(page, "Models")
    page.locator(".model-card", has_text="Zero").click()
    drawer(page).get_by_role("button", name="+ Write about it").click()
    expect(page.locator("aside.drawer")).to_have_count(0)                # the panel closed
    expect(page.locator(".bn-editor .mention")).to_contain_text("Zero", timeout=20000)
    expect(page.locator(".journal-links")).to_contain_text("Zero")
    page.get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Delete", exact=True).last.click()
    expect(page).to_have_url(BASE + "/journal")


@step("Journal: 'bought it and started' offers In progress; Yes moves the kit")
def journal_suggestion(page):
    kit = page.request.post(f"{BASE}/api/models", data={"name": f"Kit-{MARK}", "status": "Wanted"}).json()
    go(page, "Journal")
    page.get_by_role("button", name="+ New page").click()
    page.locator(".bn-editor").click(timeout=20000)
    page.keyboard.type(f"Just bought the @Kit-{MARK}")
    page.get_by_role("option", name=re.compile(MARK)).click()
    page.keyboard.type("and started it right away")
    suggestion = page.locator(".suggestion")
    expect(suggestion).to_contain_text("Mark as In progress?", timeout=10000)
    shot(page, "d28_journal_suggestion", full=False)
    suggestion.get_by_role("button", name="Yes").click()
    expect(page.locator(".suggestion")).to_have_count(0)
    expect(page.locator(".toast")).to_contain_text("now In progress")
    model = page.request.get(f"{BASE}/api/models/{kit['model_id']}").json()
    assert model["status"] == "In progress" and model["started_on"], model


@step("Journal: a / check list item is a to-do, ticked off from the list and Home")
def journal_todo(page):
    page.locator(".bn-editor").focus()
    page.keyboard.press("Control+End")                                  # the end of the text
    page.keyboard.press("Enter")
    page.keyboard.type("/check")
    page.keyboard.press("Enter")
    page.keyboard.type(f"Prime Kit-{MARK}")
    expect(page.locator(".save-status")).to_have_text("Saved", timeout=10000)
    go(page, "Home")
    todo = page.locator(".home-card .todo", has_text=MARK)
    expect(todo).to_be_visible()
    shot(page, "d29_home_todos", full=False)
    go(page, "Journal")
    todo = page.locator(".todo", has_text=MARK)
    todo.get_by_role("checkbox").check()
    expect(todo).to_have_class(re.compile("done"))
    page.reload()
    expect(page.locator(".todo", has_text=MARK)).to_have_count(0)     # done: off the list
    open_ = page.request.get(f"{BASE}/api/journal/todos?done=true").json()
    assert any(MARK in t["text"] for t in open_), open_


@step("Top-bar search: Ctrl+K, type, Enter opens the kit")
def global_search(page):
    go(page, "Home")
    page.keyboard.press("Control+k")
    page.keyboard.type("Sherman")
    expect(page.locator(".search-results li").first).to_contain_text("Sherman")
    page.keyboard.press("Enter")
    expect(drawer(page).locator(".item-name")).to_contain_text("Sherman")
    page.keyboard.press("Escape")


@step("Journal: 'I want to buy new @paint' offers the wishlist; Yes adds it")
def journal_wishlist(page):
    go(page, "Journal")
    page.get_by_role("button", name="+ New page").click()
    page.locator(".bn-editor").click(timeout=20000)
    page.keyboard.type("I want to buy new @XF10")
    page.get_by_role("option", name=re.compile("XF10")).click()
    page.keyboard.type("paint for a new project")
    suggestion = page.locator(".suggestion", has_text="Add to wishlist?")
    expect(suggestion).to_be_visible(timeout=10000)
    suggestion.get_by_role("button", name="Yes").click()
    expect(page.locator(".toast")).to_contain_text("added to your wishlist")
    wishes = page.request.get(f"{BASE}/api/wishlist").json()
    assert any("XF10" in w["name"] and (w["notes"] or "").startswith("From the journal") for w in wishes), wishes


@step("Settings: Appearance switches light and dark; Home's Wishlist action opens + Add")
def appearance(page):
    page.get_by_role("button", name="Settings").click()
    d = drawer(page)
    d.locator("summary", has_text="Appearance").click()
    d.get_by_role("button", name="Dark").click()
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    d.get_by_role("button", name="Light").click()
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    d.get_by_role("button", name="System").click()
    page.keyboard.press("Escape")
    go(page, "Home")
    page.locator(".quick-action", has_text="Wishlist").click()
    expect(page).to_have_url(re.compile(r"/wishlist\?add=1$"))
    expect(page.get_by_label("Search the Tamiya catalogue", exact=True)).to_be_visible()
    page.keyboard.press("Escape")


@step("Build steps: an In progress kit shows the step underway")
def build_underway(page):
    d = open_model(page, "Zero")
    expect(d.locator(".steps li.underway")).to_have_count(1)
    expect(d.locator(".section-head .pill")).to_contain_text("Now:")
    shot(page, "d30_build_underway", full=False)
    page.keyboard.press("Escape")


@step("Calendar: a weekly volleyball night, a day's detail, Log the result")
def calendar(page):
    go(page, "Calendar")
    expect(page.locator(".month .day")).to_have_count(42)
    page.get_by_role("button", name="+ Add event").click()
    d = drawer(page)
    d.get_by_label("What").fill(f"Volleyball comp {MARK}")
    d.get_by_label("Hobby").select_option("volleyball")
    d.get_by_label("From").fill("19:00")
    d.get_by_label("Repeats").select_option("weekly")
    d.get_by_role("button", name="Add event").click()
    expect(page.locator(".toast")).to_contain_text("added to the calendar")
    detail = page.locator(".day-detail")
    expect(detail).to_contain_text(f"Volleyball comp {MARK}")
    assert page.locator(".day-event", has_text=MARK).count() >= 3      # every week on the grid
    shot(page, "d31_calendar")
    detail.locator(".row-button", has_text=f"Volleyball comp {MARK}").click()
    d = drawer(page)
    d.get_by_role("button", name="Log the result").click()
    d = drawer(page)
    d.get_by_label("Against").fill("Spikers")
    d.get_by_label("Sets you won").fill("3")
    d.get_by_label("Sets you lost").fill("1")
    d.get_by_role("button", name="Log it").click()
    expect(page.locator(".toast")).to_contain_text("Won 3–1")
    expect(detail.locator(".row-button", has_text=f"Volleyball comp {MARK}")).to_contain_text("Result in")
    expect(detail).to_contain_text("Volleyball vs Spikers")                    # what happened
    detail.get_by_role("button", name="Write about this day").click()
    expect(page).to_have_url(re.compile(r"/journal/\d+$"))
    page.go_back()


@step("Volleyball: the game is listed; add gear and a video")
def volleyball(page):
    go(page, "Volleyball")
    expect(page.locator(".journal-card", has_text="vs Spikers").first).to_contain_text("Won 3–1")
    expect(page.locator(".next-up")).to_contain_text(MARK)
    go(page, "Gear")
    page.get_by_role("button", name="+ Add gear").click()
    d = drawer(page)
    d.get_by_label("Name").fill(f"Court shoes {MARK}")
    d.get_by_label("Kind").fill("Shoes")
    d.locator(".condition-picker button", has_text="Worn").click()
    d.get_by_role("button", name="Add gear").click()
    card = page.locator(".model-card", has_text=MARK)
    expect(card).to_contain_text("Worn")
    go(page, "Videos")
    page.get_by_role("button", name="+ Add video").click()
    d = drawer(page)
    d.get_by_label("Title").fill(f"Float serve {MARK}")
    d.get_by_label("Link").fill("https://youtu.be/dQw4w9WgXcQ")
    d.get_by_label("Topic").fill("Serving")
    d.get_by_role("button", name="Add video").click()
    expect(page.locator(".video-card", has_text=MARK).locator("img")).to_have_attribute("src", re.compile("img.youtube.com"))
    shot(page, "d32_videos", full=False)


@step("Board games: add a game, log a play, the journal offers 'Log a play'")
def board_games(page):
    go(page, "Board games")
    page.get_by_role("button", name="+ Add game").click()
    d = drawer(page)
    d.get_by_label("Name").fill(f"Catan {MARK}")
    d.get_by_label("Fewest players").fill("3")
    d.get_by_label("Most players").fill("4")
    d.get_by_role("button", name="Add game").click()
    d = drawer(page)
    expect(d.locator(".item-name")).to_have_text(f"Catan {MARK}")
    d.get_by_role("button", name="+ Log a play").click()
    d.get_by_label("Who won").fill("Sam")
    d.get_by_role("button", name="Save play").click()
    expect(d.locator(".plays")).to_contain_text("Sam")
    page.keyboard.press("Escape")
    expect(page.locator(".model-card", has_text=MARK)).to_contain_text("Played 1 time")
    shot(page, "d33_board_games", full=False)
    # "Played @Catan" on another day's page offers to log that day's play
    go(page, "Journal")
    page.get_by_role("button", name="+ New page").click()
    page.get_by_label("Date").fill("2026-01-02")                          # not today: today's play is logged
    page.locator(".bn-editor").click(timeout=20000)
    page.keyboard.type("Played @Catan")
    page.get_by_role("option", name=re.compile(MARK)).click()
    page.keyboard.type("with Jo")
    suggestion = page.locator(".suggestion", has_text="Log a play")
    expect(suggestion).to_be_visible(timeout=10000)
    shot(page, "d34_journal_play", full=False)


def scribble(page, surface, dx=0):
    """Draw a wavy line across the canvas with the mouse (the pen tool is picked up already)."""
    box = surface.bounding_box()
    x, y = box["x"] + box["width"] * 0.3 + dx, box["y"] + box["height"] * 0.45
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 25):
        page.mouse.move(x + i * 12, y + (20 if i % 2 else -20), steps=2)
    page.mouse.up()


@step("Whiteboard page: draw on it, it saves, full screen, the journal list shows the picture")
def whiteboard(page):
    go(page, "Journal")
    page.get_by_role("button", name="+ Whiteboard").click()
    page.get_by_label("Title").fill(f"Board {MARK}")
    canvas = page.get_by_test_id("drawing-canvas")
    surface = canvas.locator(".drawing-surface")
    expect(surface.locator("canvas").first).to_be_visible(timeout=30000)
    page.wait_for_timeout(800)
    scribble(page, surface)
    expect(canvas.get_by_role("status")).to_have_text("Saved", timeout=15000)
    page_id = int(re.search(r"/journal/(\d+)", page.url).group(1))
    [board] = page.request.get(f"{BASE}/api/journal/{page_id}").json()["drawings"]
    drawn = page.request.get(f"{BASE}/api/journal/drawings/{board['drawing_id']}").json()
    assert [e["type"] for e in drawn["scene"]["elements"]] == ["freedraw"], drawn["scene"]["elements"]
    shot(page, "d35_whiteboard", full=False)
    canvas.get_by_role("button", name="Full screen").click()
    overlay = page.locator(".drawing-overlay")
    expect(overlay.locator("canvas").first).to_be_visible(timeout=30000)
    page.wait_for_timeout(500)
    scribble(page, overlay.locator(".drawing-surface"), dx=-80)
    overlay.get_by_role("button", name="Done").click()
    expect(overlay).to_have_count(0, timeout=15000)
    drawn = page.request.get(f"{BASE}/api/journal/drawings/{board['drawing_id']}").json()
    kinds = [e["type"] for e in drawn["scene"]["elements"]]
    assert kinds == ["freedraw", "freedraw"] and drawn["preview_url"], (kinds, drawn["preview_url"])
    go(page, "Journal")
    card = page.locator(".journal-card", has_text=f"Board {MARK}")
    expect(card.locator(".pill", has_text="Whiteboard")).to_be_visible()
    expect(card.locator("img.journal-thumb")).to_have_attribute("src", re.compile(r"/api/journal/drawings/\d+/preview"))


@step("Notes page: / Drawing adds a sketch, drawn full screen, shown in the page")
def sketch_block(page):
    go(page, "Journal")
    page.get_by_role("button", name="+ New page").click()
    page.get_by_label("Title").fill(f"Sketch {MARK}")
    page.locator(".bn-editor").click(timeout=20000)
    page.keyboard.type("/drawing")
    page.get_by_role("option", name=re.compile("^Drawing")).click()
    overlay = page.locator(".drawing-overlay")
    expect(overlay.locator("canvas").first).to_be_visible(timeout=30000)
    page.wait_for_timeout(500)
    scribble(page, overlay.locator(".drawing-surface"))
    overlay.get_by_role("button", name="Done").click()
    expect(overlay).to_have_count(0, timeout=15000)
    preview = page.locator(".drawing-block img")
    expect(preview).to_be_visible(timeout=15000)
    shot(page, "d36_sketch_in_page", full=False)
    preview.click()                                                   # tap the sketch to draw more
    expect(page.locator(".drawing-overlay canvas").first).to_be_visible(timeout=30000)
    page.locator(".drawing-overlay").get_by_role("button", name="Done").click()


@step("Journal Full screen: just the page, bigger writing; Exit puts it back")
def writing_mode(page):
    go(page, "Journal")
    page.locator(".journal-card").first.click()
    editor = page.locator(".journal-editor .bn-editor")
    expect(editor).to_be_visible(timeout=20000)
    normal = float(editor.evaluate("e => parseFloat(getComputedStyle(e).fontSize)"))
    page.get_by_role("button", name="⛶ Full screen").click()
    expect(page.locator(".sidebar")).to_be_hidden()
    expect(page.locator(".navbar")).to_be_hidden()
    big = float(editor.evaluate("e => parseFloat(getComputedStyle(e).fontSize)"))
    assert big > normal * 1.25, (normal, big)
    shot(page, "d38_writing_mode", full=False)
    page.get_by_role("button", name="Exit full screen").click()
    expect(page.locator(".sidebar")).to_be_visible()
    expect(page.locator("body.writing-mode")).to_have_count(0)


@step("Mood: pick a face and a word; the list, its filter, Home's week and the calendar show it")
def mood(page):
    go(page, "Journal")
    page.get_by_role("button", name="+ New page").click()
    page.get_by_label("Title").fill(f"Mood {MARK}")
    page.get_by_role("button", name="How did it feel? Set a mood").click()
    panel = page.get_by_role("group", name="Mood")
    panel.get_by_role("button", name="Good").click()
    panel.get_by_role("button", name="proud", exact=True).click()
    panel.get_by_label("Add your own word").fill("Painted")
    panel.get_by_label("Add your own word").press("Enter")
    expect(page.get_by_role("button", name="Mood: Good. Change it")).to_be_visible()
    shot(page, "d39_mood", full=False)
    panel.get_by_role("button", name="Done").click()
    expect(page.locator(".save-status")).to_have_text("Saved", timeout=10000)
    page_id = int(re.search(r"/journal/(\d+)", page.url).group(1))
    saved = page.request.get(f"{BASE}/api/journal/{page_id}").json()
    assert (saved["mood"], saved["mood_words"]) == ("good", ["proud", "painted"]), saved
    go(page, "Journal")
    card = page.locator(".journal-card", has_text=f"Mood {MARK}")
    expect(card.locator(".mood-line")).to_contain_text("Good · proud, painted")
    expect(card.locator(".card-pills .pill")).to_have_text(["Journal"])         # what kind of page
    page.get_by_role("group", name="Group by").get_by_role("button", name="Day").click()
    today = page.locator("h3.day-heading", has_text="Today")
    expect(today).to_be_visible()
    expect(today.locator(".pill")).to_be_visible()                              # the day's mood
    shot(page, "d40_journal_by_day", full=False)
    page.get_by_role("group", name="Group by").get_by_role("button", name="Month").click()
    expect(page.locator("h3.day-heading")).to_have_count(0)
    expect(page.locator("h3.section-title", has_text=re.compile(r"^\w+ \d{4}$")).first).to_be_visible()
    page.get_by_role("group", name="Group by").get_by_role("button", name="Day").click()
    page.get_by_role("button", name="Rough days").click()
    expect(page.locator(".journal-card", has_text=f"Mood {MARK}")).to_have_count(0)
    page.get_by_role("button", name="Good days").click()
    expect(page.locator(".journal-card", has_text=f"Mood {MARK}")).to_have_count(1)
    go(page, "Home")
    today = page.locator(".your-week .week-day").last
    expect(today).to_contain_text("🙂")
    go(page, "Calendar")
    expect(page.locator(".day-detail .mood-line")).to_contain_text("Felt good")


@step("Video games: the dashboard (or connecting Steam) and the games list")
def video_games(page):
    go(page, "Video games")
    expect(page.locator(".section-tabs a[aria-current=page]")).to_have_text("Dashboard")
    # Connected: the sync bar; not yet: the form to connect a profile (this never calls Steam).
    expect(page.locator(".sync-bar").or_(page.get_by_label("Steam profile"))).to_be_visible(timeout=15000)
    # Connected: profile completion against the goal comes first.
    expect(page.locator(".goal-card").or_(page.get_by_label("Steam profile"))).to_be_visible(timeout=15000)
    if page.locator(".goal-card").count():
        expect(page.locator(".goal-card")).to_contain_text("Profile completion")
        expect(page.locator(".goal-marker")).to_contain_text("Goal")
    shot(page, "d41_video_games", full=False)
    page.locator(".section-tabs").get_by_role("link", name="Games").click()
    expect(page.get_by_label("Search your games")).to_be_visible()
    expect(page.locator(".game-rows li").first.or_(page.locator(".empty", has_text="No games here"))).to_be_visible()
    # + Add a game: a link that isn't a Steam game is refused before anything asks Steam.
    page.get_by_role("button", name="+ Add a game").click()
    page.get_by_label("Steam store link or app id").fill("not a game")
    page.locator(".add-game").get_by_role("button", name="Add", exact=True).click()
    expect(page.locator(".add-game .alert")).to_contain_text("store link")
    page.locator(".add-game").get_by_role("button", name="Cancel").click()
    # A game's panel: how you compare with other players (when the community numbers are in).
    # The search, filters and headings stay pinned while the list scrolls (on a PC).
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(400)
    box = page.get_by_label("Search your games").bounding_box()
    assert box and 0 <= box["y"] < 160, box
    expect(page.locator(".game-head")).to_be_visible()
    if page.locator(".game-rows li").count():   # connected: Sync now is pinned too (not pressed - no Steam here)
        expect(page.locator(".games-pinned").get_by_role("button", name="Sync now")).to_be_visible()
    shot(page, "d44_video_games_list", full=False)
    page.mouse.wheel(0, -6000)
    page.get_by_label("Search your games").fill("Clair Obscur")
    row = page.locator(".game-row").first
    if row.count():
        row.click()
        expect(drawer(page).locator(".item-title, .section-head").first).to_be_visible()
        if drawer(page).locator(".compared").count():
            expect(drawer(page).locator(".compared")).to_contain_text("Compared with other players")
            shot(page, "d43_video_game_compared", full=False)
        page.keyboard.press("Escape")
    # A game with DLC (when the data has one): a DLC badge in the list; the panel splits the main game
    # from each DLC.
    with_dlc = [g for g in json.load(urllib.request.urlopen(f"{BASE}/api/videogames?show=started")) if g.get("dlc_count")]
    if with_dlc:
        g = max(with_dlc, key=lambda g: g["dlc_count"])
        page.get_by_label("Search your games").fill(g["name"])
        row = page.locator(".game-rows li", has_text=g["name"]).first
        expect(row.locator(".dlc-badge")).to_be_visible()
        row.click()
        expect(drawer(page).locator(".dlc-group")).to_have_count(g["dlc_count"] + 1)   # main game + each DLC
        expect(drawer(page).locator(".dlc-group").first).to_contain_text("Main game")
        drawer(page).locator(".dlc-group summary").nth(1).click()
        expect(drawer(page).locator(".dlc-group").nth(1).locator(".achievements li").first).to_be_visible()
        shot(page, "d45_video_game_dlc", full=False)
        page.keyboard.press("Escape")
    page.get_by_label("Search your games").fill("")
    page.locator(".section-tabs").get_by_role("link", name="Stats").click()
    expect(page.locator(".chart")).to_have_count(4)
    slot = page.locator(".chart-slot").first
    slot.hover()
    expect(page.locator(".chart-tip")).to_be_visible()                       # hover tooltip
    page.locator(".chart-table summary").first.click()
    expect(page.locator(".chart-table table").first).to_be_visible()         # the table view
    shot(page, "d42_video_game_stats")


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
    expect(page.locator(".home-stat").first).to_be_visible(timeout=15000)
    shot(page, "m00_home", full=False)
    expect(page.locator(".tabbar")).to_be_visible()             # tabs at the bottom on phones
    expect(page.locator(".sidebar")).to_be_hidden()             # no sidebar
    expect(page.locator(".tabbar a[aria-current=page]")).to_have_text("Home")
    expect(page.locator(".tabbar a")).to_have_text(["Home", "Journal", "Calendar", "Supplies", "Hobbies"])
    page.locator(".tabbar a", has_text="Supplies").click()
    expect(page).to_have_url(BASE + "/supplies")
    expect(page.locator(".section-tabs a[aria-current=page]")).to_have_text("Supplies")
    expect(page.locator("tr.row").first).to_be_visible()
    shot(page, "m01_inventory", full=False)
    expect(page.get_by_role("button", name="Scan a barcode")).to_be_visible()
    size = page.get_by_label("Search", exact=True).evaluate("e => getComputedStyle(e).fontSize")
    assert size == "16px", f"search box font {size} (iPhone zooms in below 16px)"
    page.locator("tr.row").first.click()
    expect(drawer(page)).to_be_visible()
    expect(page.locator(".tabbar")).to_be_hidden()              # a sheet covers the tab bar
    page.wait_for_timeout(400)  # let the sheet finish sliding up
    shot(page, "m02_item_panel", full=False)
    page.keyboard.press("Escape")
    def fits(name):
        page.wait_for_timeout(300)
        safe = re.sub(r"\W+", "_", name.lower())
        shot(page, f"m_{safe}", full=False)
        width = page.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"{name} is {width}px wide on a 390px phone"

    page.locator(".section-tabs a", has_text="Wishlist").click()
    expect(page.locator(".tabbar a[aria-current=page]")).to_have_text("Supplies")
    fits("Wishlist")
    for tab in ("Journal", "Calendar"):
        page.locator(".tabbar a", has_text=tab).click()
        fits(tab)
    page.locator(".tabbar a", has_text="Hobbies").click()
    expect(page.locator(".hobby-card")).to_have_count(4)
    fits("Hobbies")
    for hobby, tabs in (("Models", ("Kits", "Colours")), ("Board games", ("Games", "Plays")),
                        ("Volleyball", ("Games", "Gear", "Videos")), ("Video games", ("Dashboard", "Games", "Stats"))):
        page.locator(".tabbar a", has_text="Hobbies").click()
        page.locator(".hobby-head", has_text=hobby).click()
        for tab in tabs:
            page.locator(".section-tabs a", has_text=tab).click()
            expect(page.locator(".tabbar a[aria-current=page]")).to_have_text("Hobbies")
            fits(f"{hobby} {tab}")
    page.locator(".tabbar a", has_text="Hobbies").click()
    page.locator(".hobby-head", has_text="Models").click()
    page.locator(".model-card", has_text="Zero").click()
    page.wait_for_timeout(400)
    shot(page, "m06_model_panel", full=False)
    button = page.get_by_role("button", name="Start timer").bounding_box()
    assert button["height"] >= 44, f"Start timer is {button['height']}px tall (44 for a finger)"


with sync_playwright() as p:
    browser = p.chromium.launch()
    # The user's time zone: "today" in the browser must be the same day the app dates pages by.
    zone = "Australia/Brisbane"
    desk = browser.new_page(viewport={"width": 1280, "height": 860}, timezone_id=zone)
    watch(desk, "desktop")
    for fn in (home, inventory_loads, search, chip, groups, condition_low, plus_minus, notes, edit_details, settings,
               add_lookup, add_to_wishlist, wishlist_buy, delete_bought, scan_owned, scan_unknown,
               models, model_paste, add_model_hasegawa, undo, add_to_wishlist_button, duplicate_check, wishlist_panel, shop_tamiya, used_up,
               scalemates, desktop_tabs, model_edit, lists_protect, kit_paints, timer, build_log, stash, mixes,
               matches, used_on, gundam, bandai_lookup, warhammer, journal_write, journal_links, journal_from_model,
               journal_suggestion, journal_todo, global_search, journal_wishlist, appearance,
               build_underway, calendar, volleyball, board_games, whiteboard, sketch_block, writing_mode, mood, video_games, settings_more, no_panel):
        fn(desk)
    ctx = browser.new_context(**p.devices["iPhone 13"], timezone_id=zone)
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
