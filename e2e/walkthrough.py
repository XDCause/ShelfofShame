"""End-to-end walk-through of Off the Clock in a real (headless) browser.

Outside websites (shops, Steam, Bunnings...) are stand-ins in the copy this runs against (OUTSIDE_SITES=stand-ins,
api/app/stand_ins.py): no step asks a real site. The weekly site check is what looks at the real ones.

Run it with .\\run_e2e.ps1 (backs up first and restores afterwards - this script changes data).
Runs inside the Playwright container on the app's Docker network, against http://web.
Prints a PASS/FAIL line per step, all browser errors, and saves screenshots to /out.
Written against the user's real data (the Zero and P-40E models, XF-1 etc.); item counts are
read from the API at the start, so adding or removing supplies doesn't break it.
"""
import base64
import json
import re
import struct
import time
import traceback
import urllib.parse
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
CHESS = bool(json.load(urllib.request.urlopen(f"{BASE}/api/chess/account"))["username"])   # Home gets a rating tile
_reading = json.load(urllib.request.urlopen(f"{BASE}/api/reading/summary"))
READING = (any(_reading["counts"].values())) + bool(_reading["reading"])   # Home: books this year (+ reading now)
HIKING = bool(json.load(urllib.request.urlopen(f"{BASE}/api/hiking/summary"))["all_time"]["hikes"])   # Home: km hiked
_garden = json.load(urllib.request.urlopen(f"{BASE}/api/garden/summary"))
GARDEN = bool(_garden["growing"] or _garden["spaces"])                                  # Home: plants growing
SHOOTING = bool(json.load(urllib.request.urlopen(f"{BASE}/api/shooting/summary"))["all_time"]["sessions"])   # Home: rounds this year
_travel = json.load(urllib.request.urlopen(f"{BASE}/api/travel/summary"))
TRAVEL = bool(_travel["now"] or _travel["upcoming"] or _travel["countries_been"])          # Home: the next trip / countries
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
    # Every failed request names its address (the browser's own "Failed to load resource" line doesn't).
    page.on("response", lambda r: r.status >= 400 and errors.append(f"[{label}] HTTP {r.status} {r.url}"))


# ---------------------------------------------------------------- desktop
@step("Home: greeting, every hobby's tiles, Coming up, and the numbers open their pages")
def home(page):
    page.goto(BASE)
    expect(page.locator(".hero h2")).to_have_text(re.compile("^Good (morning|afternoon|evening)(, .+)?$"), timeout=15000)   # (+ your name, if set)
    stats = page.locator(".home-stat")
    expect(stats.filter(has_text="Supplies")).to_contain_text(str(TOTAL))
    for tile in ("Shelf of shame", "Board games", "Volleyball", "Next game"):
        expect(stats.filter(has_text=tile)).to_be_visible()
    expect(stats).to_have_count(11 + CHESS + READING + HIKING + GARDEN + SHOOTING + TRAVEL)
    expect(page.locator(".home-card", has_text="Recent activity").locator(".pill").first).to_be_visible()
    expect(page.locator(".home-card", has_text="Coming up")).to_be_visible()
    expect(page.locator(".quick-action")).to_have_count(14)       # + Log a chess game, Add a book, Log a hike, Add a plant, Start shooting, Plan a trip
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


@step("Add panel: one box for Tamiya and Trumpeter - asked which when both have the number; a Tamiya code fills the form")
def add_lookup(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    d = drawer(page)
    box = d.get_by_placeholder("e.g. XF-76, 81776, 08005, MS-106 or nipper")
    # a number both makers use (stand-ins): you're asked which; then one only Trumpeter has: filled straight in
    box.fill("08888")
    d.get_by_role("button", name="Look up").click()
    which = d.get_by_role("region", name="Which one")
    expect(which).to_contain_text("Tamiya and Trumpeter both have item 08888")
    which.get_by_role("button", name=re.compile("^Trumpeter")).click()
    expect(d.get_by_label("Name / colour")).to_have_value(re.compile("Stand-in Trumpeter Tool", re.I))   # (names are tidied)
    expect(which).to_have_count(0)
    box.fill("08005")
    d.get_by_role("button", name="Look up").click()
    expect(d.get_by_label("Name / colour")).to_have_value("Masking Tape Cutter")
    expect(d.get_by_role("alert")).to_contain_text("Found at Trumpeter")
    # Stedi tools: words list their matches (stand-ins); picking one fills it in, with their US$ price as a guide
    box.fill("nipper")
    d.get_by_role("button", name="Look up").click()
    expect(d).to_contain_text("2 Stedi tools match")                        # the nipper, and the kit that has one
    d.get_by_role("button", name=re.compile("^MS-106")).click()
    expect(d.get_by_label("Name / colour")).to_have_value(re.compile("MS-106"))
    expect(d.get_by_role("alert")).to_contain_text("US$25.99")
    box.fill("XF-2")
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
    kits = json.load(urllib.request.urlopen(f"{BASE}/api/models/summary"))["all_kits"]   # every bought kit
    spent = "—" if kits["unpriced"] == kits["kits"] else f"${kits['value']:,.2f}"           # none priced: no $0.00
    expect(page.locator(".stat-grid")).to_contain_text(f"Spent on kits{spent}")
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
    # The "what it's for" boxes fit their text: nothing cut off, no blank line under a short note.
    for box in d.locator(".checklist textarea.purpose").all():
        spare, hidden = box.evaluate("e => [e.clientHeight - e.scrollHeight, e.scrollHeight - e.clientHeight]")
        assert hidden <= 1 and spare <= 1, (box.input_value(), spare, hidden)
    # One paint onto the wishlist from its own row, then the rest with the button at the top.
    d.locator(".checklist .wish-btn").first.click()
    expect(d.locator(".save-flash")).to_contain_text("Added to wishlist")
    expect(d.locator(".checklist li", has_text="On wishlist")).not_to_have_count(0)
    rest = d.get_by_role("button", name=re.compile("missing to wishlist"))
    if rest.count():
        rest.click()
        expect(d.locator(".save-flash")).to_contain_text(re.compile("Added to wishlist|Nothing new"))
    d.get_by_label("Have Old silver tin").check()
    expect(d).to_contain_text("2/3")
    page.keyboard.press("Escape")


@step("Add model: Trumpeter lookup by item number (stand-in)")
def add_model_trumpeter(page):
    page.get_by_role("button", name="+ Add model").click()
    d = drawer(page)
    d.get_by_role("button", name="Trumpeter", exact=True).click()
    d.get_by_placeholder("e.g. 00968").fill("00968")
    d.get_by_role("button", name="Look up").click()
    expect(d.get_by_label("Model name")).to_have_value("German Leopard2A6 MBT")
    expect(d.get_by_label("Scale", exact=True)).to_have_value("1/16")
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


def set_model(page, name, **fields):
    """Put a kit in the state a step needs first (the real data moves on; the run restores it after)."""
    [kit] = [m for m in page.request.get(f"{BASE}/api/models").json() if name in m["name"]]
    r = page.request.patch(f"{BASE}/api/models/{kit['model_id']}", data=fields)
    assert r.ok, r.text()


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
    d.locator(".log-form input[data-source=gallery]").set_input_files([       # several at once
        {"name": "hull.png", "mimeType": "image/png", "buffer": PIXEL},
        {"name": "tracks.png", "mimeType": "image/png", "buffer": PIXEL}])
    expect(d.locator(".log-photos.picked li")).to_have_count(2)
    d.get_by_role("button", name="Add to log").click()
    entry = d.locator(".log > li").first
    expect(entry).to_contain_text("Hull assembled")
    expect(entry.locator(".log-photos img")).to_have_count(2)
    expect(entry.locator(".log-photos img").first).to_be_visible()
    # Edit it: a new note, one photo less, one more added.
    entry.get_by_role("button", name=re.compile("^Edit the entry")).click()
    entry.get_by_label("Edit the note").fill("Hull assembled and primed")
    entry.get_by_role("button", name="Remove photo 1").click()
    entry.locator("input[data-source=gallery]").set_input_files([
        {"name": "primer.png", "mimeType": "image/png", "buffer": PIXEL}])
    entry.get_by_role("button", name="Save").click()
    entry = d.locator(".log > li").first
    expect(entry).to_contain_text("Hull assembled and primed")
    expect(entry.locator(".log-photos img")).to_have_count(2)
    shot(page, "d18_build_log", full=False)
    page.keyboard.press("Escape")


@step("Kit stash: price paid shows on the model and in the stash value")
def stash(page):
    set_model(page, "Sherman", status="In stash")             # a Wanted kit's price isn't in the stash
    d = open_model(page, "Sherman")
    d.get_by_role("button", name="Edit details").click()
    d = drawer(page)
    expect(d.get_by_label("Bought from")).to_be_visible()
    d.get_by_label("Price paid ($)").fill("54.95")
    page.get_by_role("button", name="Save details").click()
    expect(drawer(page)).to_contain_text("Paid $54.95")
    page.keyboard.press("Escape")
    stash = page.request.get(f"{BASE}/api/models/summary").json()["shelf_of_shame"]["value"]   # every kit in it
    expect(page.locator(".stat-grid")).to_contain_text(f"${stash:,.2f}")
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
    set_model(page, "RX-78-2", status="In stash", stage=None)       # in the box, no steps done
    d = open_model(page, "RX-78-2")
    expect(d.locator(".item-sub").first).to_contain_text("HG · 1/144 · Bandai · G5057403")
    expect(d.locator(".steps button")).to_have_count(5)                      # ... Top coat, Complete
    expect(d.locator(".checklist li", has_text="Panel Line Gray")).to_contain_text("In inventory")
    d.locator(".steps button", has_text="Panel lined").click()
    expect(d.locator(".steps button[aria-pressed='true']")).to_have_count(2)   # Built + Panel lined
    expect(d.locator(".status-picker [aria-pressed='true']")).to_have_text("In progress")
    shot(page, "d23_gundam", full=False)
    d.locator(".steps button", has_text="Panel lined").click()                 # untick: back to Built
    expect(d.locator(".steps button[aria-pressed='true']")).to_have_count(1)
    # No detailing on a snap-fit kit: Built -> Complete skips the steps between and finishes it.
    d.locator(".steps button", has_text="Complete").click()
    expect(d.locator(".steps li.skipped")).to_have_count(3)
    expect(d.locator(".status-picker [aria-pressed='true']")).to_have_text("Finished")
    d.locator(".steps button", has_text="Panel lined").click()                 # did panel line it after all
    expect(d.locator(".steps li.skipped")).to_have_count(2)
    shot(page, "d23b_gundam_skipped", full=False)
    d.locator(".steps button", has_text="Complete").click()                    # not finished: back to Panel lined
    expect(d.locator(".status-picker [aria-pressed='true']")).to_have_text("In progress")
    d.locator(".steps button", has_text="Panel lined").click()                 # and back to Built
    expect(d.locator(".steps button[aria-pressed='true']")).to_have_count(1)
    expect(d.locator(".steps li.skipped")).to_have_count(0)
    page.keyboard.press("Escape")
    # In progress, Built: the next step shows as underway
    expect(page.locator(".model-card", has_text="RX-78-2")).to_contain_text("Panel lining · step 2 of 5")
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
    # Games Workshop: "(new)" until you've used it (a Warhammer lookup adds it), else your brand.
    expect(d.get_by_label("Brand").locator("option:checked")).to_have_text(re.compile(r"^Games Workshop( \(new\))?$"))
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


@step("Banners: your name in Home's greeting; a picture of your own on a page's banner, moved, then the drawing back")
def banners(page):
    go(page, "Home")
    expect(page.locator(".home-banner .landscape")).to_have_count(1)            # no picture yet: a drawn landscape
    page.get_by_role("button", name="Settings").click()
    d = drawer(page)
    d.locator("summary", has_text="Appearance").click()
    d.get_by_label("Your name").fill("Sam")
    d.get_by_label("Your name").press("Enter")
    expect(d).to_contain_text("Saved")
    page.keyboard.press("Escape")
    expect(page.locator(".hero h2")).to_have_text(re.compile("^Good (morning|afternoon|evening), Sam$"))
    page.goto(BASE + "/boardgames")
    banner = page.locator(".page-banner")
    expect(banner.locator(".banner-title")).to_have_text("Board games")
    expect(banner.locator(".banner-tagline")).to_be_visible()
    banner.get_by_label("Change the Board games picture").click()
    banner.locator(".banner-picture-menu input[type=file]").set_input_files(
        {"name": "table.png", "mimeType": "image/png", "buffer": PIXEL})
    expect(banner.locator("img.banner-photo")).to_have_count(1)
    expect(banner.locator(".landscape")).to_have_count(0)
    banner.get_by_label("Change the Board games picture").click()
    banner.get_by_role("button", name="Show more of the top").click()
    expect(banner.locator("img.banner-photo")).to_have_attribute("style", re.compile("40%"))
    banner.get_by_label("Change the Board games picture").click()
    banner.get_by_role("button", name="Use the drawing again").click()
    expect(banner.locator(".landscape")).to_have_count(1)
    page.mouse.wheel(0, 600)                                                     # scrolled: the bar shows the page's name
    expect(page.locator(".navbar.scrolled h1")).to_contain_text("Board games")
    page.get_by_role("button", name="Settings").click()                          # tidy up: no name again
    d.locator("summary", has_text="Appearance").click()
    d.get_by_label("Your name").fill("")
    d.get_by_label("Your name").press("Enter")
    page.keyboard.press("Escape")


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
    set_model(page, "Zero", status="In progress")
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
    # An all-day event: the switch hides the times; it shows as a solid bar and "All day".
    page.get_by_role("button", name="+ Add event").click()
    d = drawer(page)
    d.get_by_label("What").fill(f"Track day {MARK}")
    d.get_by_role("switch", name="All day").check()
    expect(d.get_by_label("From")).to_have_count(0)
    d.get_by_label("Hobby").select_option("car")                              # any hobby can have events
    d.get_by_role("button", name="Add event").click()
    expect(page.locator(".day-event.all-day", has_text=f"Track day {MARK}")).to_be_visible()
    expect(detail.locator(".row-button", has_text=f"Track day {MARK}")).to_contain_text("All day")
    detail.locator(".row-button", has_text=f"Track day {MARK}").click()
    d = drawer(page)
    expect(d.get_by_role("switch", name="All day")).to_be_checked()          # opens as all day
    d.get_by_role("button", name="Delete", exact=True).click()
    d.locator(".confirm").get_by_role("button", name="Delete").click()
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
    expect(page.locator(".vb-row", has_text="vs Spikers").first).to_contain_text("Won 3–1")
    expect(page.locator(".next-up")).to_contain_text(MARK)
    # Register a team with where it plays, as the default: a new game starts with both.
    page.get_by_role("button", name="+ Add team").click()
    d = drawer(page)
    d.get_by_label("Team name").fill(f"Team {MARK}")
    d.get_by_label("Where they play").fill(f"Hall {MARK}")
    d.get_by_label("New games start with this team").check()
    d.get_by_role("button", name="Add team").click()
    expect(page.locator(".team-chip", has_text=f"Team {MARK}")).to_contain_text("Default")
    page.get_by_role("button", name="+ Log a game").click()
    d = drawer(page)
    expect(d.get_by_label("Your team").locator("option:checked")).to_have_text(f"Team {MARK}")
    expect(d.get_by_label("Where")).to_have_value(f"Hall {MARK}")
    shot(page, "d31b_volleyball_defaults", full=False)
    # A bye: no opponent or sets to fill in; a bye win counts as a win.
    d.get_by_role("group", name="Played or a bye").get_by_role("button", name="Bye – win").click()
    expect(d.get_by_label("Against")).to_have_count(0)
    d.get_by_role("button", name="Log it").click()
    expect(page.locator(".vb-row", has_text="Bye").first).to_contain_text("Bye – win")
    expect(page.locator(".stat-grid")).to_contain_text("incl. 1 bye")
    go(page, "Gear")
    page.get_by_role("button", name="+ Add gear").first.click()
    d = drawer(page)
    d.get_by_label("Name").fill(f"Court shoes {MARK}")
    d.get_by_label("Kind").fill("Shoes")
    d.locator(".condition-picker button", has_text="Worn").click()
    d.get_by_role("button", name="Add gear").click()
    card = page.locator(".model-card", has_text=MARK)
    expect(card).to_contain_text("Worn")
    # A photo pasted in (Ctrl+V of a picture copied in the browser) instead of picked from a file.
    card.first.click()
    d = drawer(page)
    d.get_by_role("button", name="Paste or link").click()
    d.get_by_label("Paste a picture or its web address").evaluate("""(box) => {
        const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='),
                                    (c) => c.charCodeAt(0))
        const data = new DataTransfer()
        data.items.add(new File([png], 'copied.png', { type: 'image/png' }))
        box.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }))
    }""")
    expect(d.locator(".row-photo img")).to_be_visible(timeout=15000)
    page.keyboard.press("Escape")
    # Gear you want: its own group; marking it New dates it bought today.
    page.get_by_role("button", name="+ Want").click()
    d = drawer(page)
    expect(d.get_by_role("group", name="Condition").get_by_role("button", name="Wanted")).to_have_attribute("aria-pressed", "true")
    expect(d.get_by_label("Bought on")).to_have_count(0)                      # not bought yet: no date or price
    expect(d.get_by_label("Price paid")).to_have_count(0)
    d.get_by_label("Name").fill(f"Ball {MARK}")
    d.get_by_role("button", name="Add to wanted").click()
    expect(page.locator(".gear-wanted-title")).to_be_visible()
    wanted = page.locator(".model-card", has_text=f"Ball {MARK}")
    expect(wanted.locator(".status-badge")).to_have_text("Wanted")
    expect(page.locator(".summary")).to_contain_text("wanted")
    wanted.click()
    d = drawer(page)
    d.get_by_role("group", name="Condition").get_by_role("button", name="New").click()
    expect(d.get_by_label("Bought on")).to_be_visible()                       # bought: they're back (left empty = today)
    d.get_by_role("button", name="Save", exact=True).click()
    expect(wanted.locator(".status-badge")).to_have_text("New")
    expect(wanted).to_contain_text("Bought")
    go(page, "Videos")
    page.get_by_role("button", name="+ Add video").first.click()
    d = drawer(page)
    d.locator(".video-pick input[data-source=gallery]").set_input_files(        # an uploaded video, not a link
        {"name": "serve.mp4", "mimeType": "video/mp4", "buffer": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 512})
    expect(d.locator(".video-pick")).to_contain_text("serve.mp4")
    d.get_by_label("Title").fill(f"Float serve {MARK}")
    d.get_by_label("Topic").fill("Serving")
    d.get_by_role("button", name="Add video").click()
    card = page.locator(".video-card", has_text=MARK)
    expect(card.locator("video")).to_have_attribute("src", re.compile(r"/api/volleyball/videos/\d+/file"))
    expect(card.locator(".edit-pill")).to_have_text("Raw")                      # an upload is raw footage
    shot(page, "d32_videos", full=False)
    card.get_by_role("button", name=f"Float serve {MARK}", exact=True).click()   # its panel has the player
    d = drawer(page)
    expect(d.locator("video.video-player")).to_be_visible()
    # Clips: a bookmarked part (added through the API - the test browser can't play MP4), ticked
    # for a highlight video.
    video_id = int(re.search(r"/videos/(\d+)/file", d.locator("video.video-player").get_attribute("src")).group(1))
    page.request.post(f"{BASE}/api/volleyball/videos/{video_id}/clips", data={"title": "Ace", "start": 0, "end": 0.5})
    page.keyboard.press("Escape")
    card.get_by_role("button", name=f"Float serve {MARK}", exact=True).click()
    d = drawer(page)
    expect(d.locator(".clip-list li", has_text="Ace")).to_contain_text("0:00.0 – 0:00.5")
    expect(d.get_by_role("button", name="Tick clips to make a highlight video")).to_be_disabled()
    d.get_by_label("Use Ace in a highlight video").check()
    expect(d.get_by_role("button", name=re.compile(r"^Make a highlight video \(1 clip"))).to_be_enabled()
    expect(d.get_by_role("link", name="Download")).to_have_attribute("href", re.compile(r"download=true"))
    # Delete it: its file goes too (the data restore after the run can't take files off the disk).
    d.get_by_role("button", name="Delete", exact=True).click()
    d.locator(".confirm").get_by_role("button", name="Delete").click()
    expect(page.locator(".video-card", has_text=MARK)).to_have_count(0)


@step("Board games: add a game, log a play, the journal offers 'Log a play'")
def board_games(page):
    go(page, "Board games")
    page.get_by_role("button", name="+ Add game").click()
    d = drawer(page)
    expect(d.get_by_label("Find a board game", exact=True)).to_be_visible()   # (not searched: no shop call here)
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
    if page.locator(".goal-card").count():
        expect(page.locator(".home-card-title", has_text="Quick wins")).to_be_visible()
        expect(page.locator(".home-card-title", has_text="Epic and Ubisoft")).to_be_visible()
        expect(page.locator(".vg-playtime")).to_contain_text("This week")          # playtime over time
        expect(page.locator(".vg-playtime .chart")).to_be_visible()
    # Epic / Ubisoft games: the dashboard counts every platform; with all on, tapping Steam means
    # Steam alone (matches SteamHunters); a second platform can be added back; All turns them all on.
    toggles = page.get_by_role("group", name="Platforms to count")
    if page.locator(".goal-card").count() and toggles.count():
        everything = page.locator(".goal-percent").inner_text()
        toggles.get_by_role("button", name="Steam").click()
        expect(toggles).to_contain_text("matches SteamHunters")
        expect(toggles.get_by_role("button", name="Steam")).to_be_disabled()      # the last one stays on
        page.wait_for_timeout(500)
        print(f"    profile completion: all {everything}, Steam only {page.locator('.goal-percent').inner_text()}")
        others = [p for p in ("Epic", "Ubisoft") if toggles.get_by_role("button", name=p).count()]
        toggles.get_by_role("button", name=others[0]).click()                      # adds it: Steam stays on
        expect(toggles.get_by_role("button", name="Steam")).to_have_attribute("aria-pressed", "true")
        expect(toggles.get_by_role("button", name=others[0])).to_have_attribute("aria-pressed", "true")
        toggles.get_by_role("button", name="All", exact=True).click()
        expect(toggles).not_to_contain_text("matches SteamHunters")
        expect(toggles.get_by_role("button", name="All", exact=True)).to_have_count(0)
    shot(page, "d41_video_games", full=False)
    page.locator(".section-tabs").get_by_role("link", name="Games").click()
    expect(page.get_by_label("Search your games")).to_be_visible()
    expect(page.locator(".game-rows li").first.or_(page.locator(".empty", has_text="No games here"))).to_be_visible()
    # The toolbar: Sync now (when connected) and Find a game - adding games is in Find a game.
    expect(page.locator(".games-pinned .toolbar").get_by_role("button", name=re.compile(r"^\+ Add"))).to_have_count(0)
    # Find a game: scout any Steam game by name (stand-ins for Steam's store search + SteamHunters here).
    page.get_by_role("button", name="Find a game").click()
    page.get_by_label("Search Steam").fill("hollow knight")
    expect(page.locator(".find-games li").first.or_(page.locator(".drawer .alert"))).to_be_visible(timeout=30000)
    if page.locator(".find-games li").count():
        expect(page.locator(".find-games")).not_to_contain_text("Soundtrack")
        page.locator(".find-games li").first.click()
        expect(page.locator(".drawer .section-head").or_(page.locator(".drawer .alert"))).to_be_visible(timeout=30000)
        shot(page, "d44b_find_a_game", full=False)
        if page.locator(".drawer .section-head").count():
            expect(page.locator(".drawer .section-head")).to_contain_text("achievements")
        page.get_by_role("button", name="‹ Back to results").click()
        expect(page.get_by_label("Search Steam")).to_have_value("hollow knight")   # the search is kept
    else:
        print("    Steam's store search couldn't be reached - skipped")
    # Epic: a game without achievements (like Fortnite) added by hand, tracked by its hours.
    d = drawer(page)
    d.get_by_role("group", name="Where to search").get_by_role("button", name="Epic Games").click()
    d.get_by_label("Search Epic Games").fill(f"hoursgame {MARK}")
    by_hand = d.get_by_role("button", name=re.compile("to your Epic Games games"))
    expect(by_hand).to_contain_text("Hoursgame", timeout=30000)               # typed in lower case: a name's capitals
    by_hand.click()
    d = drawer(page)
    d.get_by_label("Hours played").fill("569")
    d.get_by_role("button", name="Add game").click()
    d = drawer(page)
    expect(d.locator(".section-head")).to_contain_text("No achievements")
    expect(d.get_by_role("button", name="Add a photo")).to_be_visible()     # your own picture for it
    expect(d.get_by_label("Hours played")).to_have_value("569")
    d.get_by_role("button", name="Remove").click()
    expect(page.locator(".drawer")).to_have_count(0)
    page.keyboard.press("Escape")
    # A game's panel: how you compare with other players (when the community numbers are in).
    # The search, filters and headings stay pinned while the list scrolls (on a PC).
    page.mouse.wheel(0, 3000)
    page.wait_for_timeout(400)
    box = page.get_by_label("Search your games").bounding_box()
    assert box and 0 <= box["y"] < 160, box
    expect(page.locator(".game-head")).to_be_visible()
    if page.locator(".game-rows li").count():   # connected: Sync now is pinned too (not pressed - no Steam here)
        expect(page.locator(".games-pinned").get_by_role("button", name="Sync now")).to_be_visible()
        hide = page.get_by_role("button", name="Hide 100%")                     # 100% games out of the list, and back
        hide.click()
        expect(hide).to_have_attribute("aria-pressed", "true")
        expect(page.locator(".game-rows .perfect-badge")).to_have_count(0)
        hide.click()
        expect(hide).to_have_attribute("aria-pressed", "false")
    names = page.locator(".game-rows .game-name .item-title")                              # a heading clicked twice reverses
    if names.count() > 1:
        game_head = page.locator(".game-head").get_by_role("button", name="Game", exact=True)
        game_head.click()
        first = names.first.inner_text()
        game_head.click()
        expect(game_head).to_contain_text("▴")
        expect(names.first).not_to_have_text(first)
        game_head.click()
        expect(names.first).to_have_text(first)
        page.get_by_label("Sort games").select_option("played")
    shot(page, "d44_video_games_list", full=False)
    page.mouse.wheel(0, -6000)
    page.get_by_label("Search your games").fill("Clair Obscur")
    row = page.locator(".game-row").first
    if row.count():
        row.click()
        expect(drawer(page).locator(".item-title, .section-head").first).to_be_visible()
        expect(drawer(page).get_by_role("button", name="Sync this game")).to_be_visible()   # not pressed: no Steam here
        search = drawer(page).get_by_label("Search achievements")
        if search.count():                                                     # search its achievements
            search.fill("zzqq no such achievement")
            expect(drawer(page)).to_contain_text("0 matches")
            search.fill("")
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
    # Epic / Ubisoft (when an Exophase profile is connected): the same table; a Ubisoft game's panel
    # lists its achievements (from its Steam version) to tick off.
    toggles = page.get_by_role("group", name="Platforms to count")
    if toggles.count():
        expect(page.locator(".game-rows .pill.platform-steam").first).to_be_visible()   # all together, each row says where
        toggles.get_by_role("button", name="Ubisoft").click()                           # all on: a tap = Ubisoft only
        expect(page.locator(".game-rows .pill.platform-steam")).to_have_count(0)
        page.locator(".game-rows li").first.click()
        d = drawer(page)
        expect(d.locator(".section-head")).to_contain_text("Ubisoft")
        if d.locator(".ach-tick").count():
            before = d.locator(".section-head strong").inner_text()
            d.locator(".ach-tick").first.click()
            expect(d.locator(".section-head strong")).not_to_have_text(before)
            expect(d.locator(".section-head .hand-ticked")).to_have_text("*")      # ticked by hand, not synced
            expect(d.get_by_label("Count it in my completion, goal and totals")).to_be_visible()
        shot(page, "d47_ubisoft_game", full=False)
        page.keyboard.press("Escape")
        toggles.get_by_role("button", name="Epic").click()
        toggles.get_by_role("button", name="Ubisoft").click()                           # Epic only
        expect(page.locator(".game-rows li").first).to_be_visible()
        shot(page, "d48_epic_games", full=False)
        toggles.get_by_role("button", name="All", exact=True).click()                   # all three again
        expect(toggles.get_by_role("button", name="Steam")).to_have_attribute("aria-pressed", "true")
    page.locator(".section-tabs").get_by_role("link", name="Stats").click()
    # This month's recap (back a month and forward again), then the unlock calendar.
    recap = page.locator(".recap")
    expect(recap.locator(".home-card-title")).to_be_visible()
    this_month = recap.locator(".home-card-title").inner_text()
    if recap.get_by_role("button", name="Month before").is_enabled():
        recap.get_by_role("button", name="Month before").click()
        expect(recap.locator(".home-card-title")).not_to_have_text(this_month)
        recap.get_by_role("button", name="Month after").click()
        expect(recap.locator(".home-card-title")).to_have_text(this_month)
    expect(page.locator(".heatmap-week")).to_have_count(53)
    page.locator(".heatmap-grid .heatmap-day").last.hover()
    expect(page.locator(".heatmap-foot")).to_contain_text("on ")
    shot(page, "d46_video_game_recap", full=False)
    expect(page.locator(".home-card:not(.recap) > .chart")).to_have_count(4)
    slot = page.locator(".chart-slot").first
    slot.hover()
    expect(page.locator(".chart-tip")).to_be_visible()                       # hover tooltip
    page.locator(".chart-table summary").first.click()
    expect(page.locator(".chart-table table").first).to_be_visible()         # the table view
    shot(page, "d42_video_game_stats")


@step("Chess: the dashboard (or connecting chess.com), an over-the-board game replayed on the board, openings")
def chess(page):
    go(page, "Chess")
    expect(page.locator(".sync-bar, .steam-setup").first).to_be_visible()     # connected, or the connect form
    page.locator(".section-tabs").get_by_role("link", name="Games").click()
    page.get_by_role("button", name="+ Log an over-the-board game").click()
    page.get_by_label("Opponent").fill(f"Rival-{MARK}")
    page.get_by_label("Result").select_option("win")
    page.get_by_label("Opening").fill("Ruy Lopez Opening Morphy Defense")
    page.get_by_label("Moves (PGN, optional - to replay it here)").fill("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6")
    page.get_by_role("button", name="Add game").click()
    d = drawer(page)
    expect(d).to_contain_text(f"vs Rival-{MARK}")
    expect(d.locator(".chess-board .sq")).to_have_count(64)
    expect(d.locator(".chess-ply")).to_contain_text("4... Nf6")                # opens at the end
    d.get_by_role("button", name="Start").click()
    d.get_by_role("button", name="Forward one move").click()
    expect(d.locator(".chess-ply")).to_contain_text("1. e4")
    expect(d.locator(".chess-board .pc")).to_have_count(32)
    shot(page, "d49_chess_game", full=False)
    page.keyboard.press("Escape")
    expect(page.locator(".chess-games")).to_contain_text(f"Rival-{MARK}")
    page.locator(".section-tabs").get_by_role("link", name="Openings").click()
    expect(page.locator(".opening", has_text="Ruy Lopez Opening")).to_be_visible()
    shot(page, "d50_chess_openings", full=False)


@step("Reading: add a book by hand, update the page, a quote, finish it with stars; books, quotes and stats pages")
def reading(page):
    go(page, "Reading")
    expect(page.locator(".goal-card, .empty-start").first).to_be_visible()
    page.locator(".section-tabs").get_by_role("link", name="Books").click()
    page.get_by_role("button", name="+ Add a book").first.click()
    d = drawer(page)
    expect(d.get_by_role("group", name="Shelf").get_by_role("button", name="On my shelf")).to_be_visible()
    d.get_by_role("group", name="Shelf").get_by_role("button", name="Reading").click()
    d.get_by_role("button", name="Not there? Type it in").click()       # (no Open Library search in the walkthrough)
    d.get_by_label("Title").fill(f"Book-{MARK}")
    d.get_by_label("Author").fill("E. Twoe")
    d.get_by_label("Pages").fill("300")
    d.get_by_role("button", name="Add book").click()
    d = drawer(page)
    expect(d.get_by_role("heading", name=f"Book-{MARK}")).to_be_visible()
    expect(d.get_by_role("group", name="Shelf").get_by_role("button", name="Reading")).to_have_attribute("aria-pressed", "true")
    d.get_by_label(f"Page you're on in Book-{MARK}").fill("120")
    d.get_by_role("button", name="Update").click()
    expect(d.locator(".book-progress")).to_contain_text("p. 120 of 300 · 40%")
    expect(d.locator(".reading-log")).to_contain_text("120 pages")
    d.get_by_role("button", name="+ Save a quote").click()
    d.get_by_label("Quote").fill(f"Words worth keeping {MARK}")
    d.get_by_label("Page", exact=True).fill("42")
    d.get_by_role("button", name="Save quote").click()
    expect(d.locator(".quote-list")).to_contain_text(f"Words worth keeping {MARK}")
    d.get_by_role("group", name="Shelf").get_by_role("button", name="Finished").click()
    d.get_by_role("button", name="4 stars").click(position={"x": 4, "y": 20})     # left edge = a half
    expect(d.get_by_role("group", name="Your rating: 3.5 out of 5")).to_be_visible()
    # A series, typed in Edit details: shown under the author, and "In this series" at the bottom (the
    # made-up series isn't on Wikidata / Open Library, so it says so).
    d.get_by_role("button", name="Edit details").click()
    d = drawer(page)
    d.get_by_label("Series", exact=True).fill(f"Saga-{MARK}")
    d.get_by_label("Number in the series").fill("2")
    page.get_by_role("button", name="Save details").click()
    d = drawer(page)
    expect(d.locator(".book-head .series-meta")).to_have_text(f"Saga-{MARK} #2")
    expect(d.get_by_role("heading", name="In this series")).to_be_visible()
    expect(d.get_by_text("Couldn't find the other books")).to_be_visible(timeout=60000)
    d.get_by_role("button", name="4 stars").click()                                # middle = whole
    expect(d.get_by_role("button", name="4 stars")).to_have_attribute("aria-pressed", "true")
    shot(page, "d51_reading_book", full=False)
    page.keyboard.press("Escape")
    page.get_by_label("Search your books").fill(MARK)
    expect(page.locator(".book-card", has_text=f"Book-{MARK}")).to_contain_text("★★★★")
    page.locator(".section-tabs").get_by_role("link", name="Quotes").click()
    expect(page.locator(".quote-wall")).to_contain_text(f"Words worth keeping {MARK}")
    page.locator(".section-tabs").get_by_role("link", name="Stats").click()
    expect(page.locator(".home-card-title", has_text="Reading calendar")).to_be_visible()
    expect(page.locator(".heatmap-week")).to_have_count(53)
    page.locator(".section-tabs").get_by_role("link", name="Dashboard").click()
    expect(page.locator(".goal-card")).to_contain_text("reading goal")
    shot(page, "d52_reading_dashboard", full=False)
    # For you: suggestions from Open Library (may refresh live), or what it needs to start.
    page.locator(".section-tabs").get_by_role("link", name="For you").click()
    expect(page.locator(".recs-section-head, .recs .empty, .empty-state, .recs .loading").first).to_be_visible(timeout=30000)
    shot(page, "d53_reading_for_you", full=False)


@step("Warhammer: an army's range from Good Games (stand-in), + Wanted adds the Combat Patrol to your kits")
def warhammer_range(page):
    go(page, "Models")
    # Open straight on the army (one range from the shop, not the remembered one and then this one).
    page.evaluate("localStorage.setItem('offtheclock.warhammerArmy', 'Adeptus Mechanicus')")
    page.locator(".section-tabs").get_by_role("link", name="Warhammer").click()
    expect(page.locator(".wh-title, .wh-range .alert").first).to_be_visible(timeout=120000)
    if page.locator(".wh-range .alert").count():                 # the shop couldn't be reached: nothing more to check
        return
    expect(page.locator(".wh-title")).to_have_text("Adeptus Mechanicus")
    card = page.locator(".wh-card", has=page.locator(".wh-code", has_text="59-05"))
    expect(card).to_contain_text("Combat Patrol: Adeptus Mechanicus")
    shot(page, "d54_warhammer_range", full=False)
    if card.get_by_role("button", name="+ Wanted").count():
        card.get_by_role("button", name="+ Wanted").click()
        expect(card.get_by_role("button", name="Yours · Wanted").or_(page.locator(".toast", has_text="Good Games"))
               ).to_be_visible(timeout=120000)
        if not card.get_by_role("button", name="Yours · Wanted").count():   # the shop said "slow down": stop here
            return
    card.get_by_role("button", name=re.compile("^Yours")).click()
    d = drawer(page)
    expect(d.locator(".item-name")).to_have_text("Combat Patrol: Adeptus Mechanicus")
    expect(d.locator(".item-sub").first).to_contain_text("Adeptus Mechanicus")
    page.keyboard.press("Escape")


@step("Warhammer minis: each mini its own step, a unit set at once, the box follows")
def warhammer_minis(page):
    kit = page.request.post(f"{BASE}/api/models", data={"name": f"Box-{MARK}", "hobby": "Warhammer", "status": "In stash",
                                                        "brand_name": "Games Workshop"}).json()
    go(page, "Models")
    page.locator(".model-card", has_text=f"Box-{MARK}").first.click()
    d = drawer(page)
    expect(d.locator(".section-title", has_text="Track each mini")).to_be_visible()
    d.get_by_role("button", name="Add them by hand").click()
    d.get_by_label("How many").fill("5")
    d.get_by_label("Unit", exact=True).fill("Skitarii Rangers")
    d.locator(".mini-add").get_by_role("button", name="Add").click()
    expect(d.locator(".mini-unit")).to_have_count(1)
    d.get_by_role("button", name="+ Add minis").click()                         # the tracker's add form starts closed
    d.get_by_label("How many").fill("1")
    d.get_by_label("Unit", exact=True).fill("Skitarii Marshal")
    d.locator(".mini-add").get_by_role("button", name="Add").click()
    expect(d.locator(".mini-unit")).to_have_count(2)
    expect(d.locator(".section-head", has_text="Minis")).to_contain_text("0 of 6 complete")
    rangers = d.locator(".mini-unit", has_text="Skitarii Rangers")
    rangers.get_by_label("This unit: set every mini to a step").select_option("Primed")
    expect(rangers.locator(".fold-detail")).to_have_text("All primed")
    rangers.get_by_role("group", name="Mini 1 steps").get_by_role("button", name="Complete").click()
    expect(d.locator(".section-head", has_text="Minis")).to_contain_text("1 of 6 complete")
    expect(d.locator(".mini-counts")).to_contain_text("Not started 1")
    model = page.request.get(f"{BASE}/api/models/{kit['model_id']}").json()
    assert (model["status"], model["figures"], model["figures_done"], model["stage"]) == ("In progress", 6, 1, None), model
    d.get_by_label("Whole box: set every mini to a step").select_option("Built")
    expect(d.locator(".mini-counts")).to_have_text("Built 6")
    shot(page, "d54b_warhammer_minis", full=False)
    page.keyboard.press("Escape")
    page.request.delete(f"{BASE}/api/models/{kit['model_id']}")


@step("Gundam: in stock now at Good Games (stand-in), a search, grade chips")
def gundam_range(page):
    go(page, "Models")
    page.locator(".section-tabs").get_by_role("link", name="Gundam").click()
    expect(page.locator(".wh-title, .wh-range .alert").first).to_be_visible(timeout=120000)
    if page.locator(".wh-range .alert").count():                 # the shop couldn't be reached
        return
    expect(page.locator(".wh-title")).to_have_text("In stock now")
    page.get_by_label("Search Gunpla").fill("rx-78-2")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.locator(".wh-title", has_text="rx-78-2").or_(page.locator(".wh-range .alert")).first).to_be_visible(timeout=120000)
    if page.locator(".wh-range .alert").count():                 # the shop said "slow down": stop here
        return
    expect(page.locator(".wh-card").first).to_be_visible()
    page.get_by_role("group", name="Grade").get_by_role("button", name=re.compile("^HG")).click()
    expect(page.locator(".wh-card .wh-code").first).to_contain_text("HG")
    shot(page, "d55_gundam_range", full=False)


@step("Volleyball Coach: a thing to fix with a link, Sorted; the starter drills and positions")
def volleyball_coach(page):
    go(page, "Volleyball")
    page.locator(".section-tabs").get_by_role("link", name="Coach").click()
    expect(page.get_by_role("button", name=re.compile(r"^\+ Add note|^\+ Add the starter")).first).to_be_visible()
    if page.get_by_role("button", name="+ Add the starter drills & positions").count():
        page.get_by_role("button", name="+ Add the starter drills & positions").click()
    elif page.get_by_role("button", name="+ Starter drills & positions").count():
        page.get_by_role("button", name="+ Starter drills & positions").click()
    expect(page.locator(".coach-card .item-title", has_text="Butterfly passing")).to_be_visible()
    expect(page.locator(".coach-card .item-title", has_text=re.compile("^Libero$"))).to_be_visible()
    page.get_by_role("button", name="+ Add note").click()
    d = drawer(page)
    d.get_by_label("Title").fill(f"Serves into the net {MARK}")
    d.get_by_label("Skill").fill("Serving")
    d.get_by_label("Notes").fill("- Toss lower\n- Watch the ball onto the hand")
    d.get_by_label("Add a link").fill("https://example.com/serving-tips")      # (a made-up YouTube link's picture would 404)
    d.get_by_role("button", name="Add", exact=True).click()
    expect(d.locator(".coach-link-list a", has_text="example.com/serving-tips")).to_be_visible()
    expect(d.get_by_role("link", name="Find videos on YouTube ↗")).to_have_attribute("href", re.compile("youtube.com/results"))
    d.get_by_role("button", name="Add note").click()
    card = page.locator(".coach-card", has_text=MARK)
    expect(card.locator(".pill")).to_have_text("Working on")
    expect(page.locator(".summary")).to_contain_text("you're working on")
    shot(page, "d57_coach", full=False)
    card.click()
    d = drawer(page)
    d.get_by_role("group", name="Status").get_by_role("button", name="Sorted").click()
    d.get_by_role("button", name="Save", exact=True).click()
    expect(card.locator(".pill")).to_have_text("Sorted")
    page.get_by_role("group", name="Show").get_by_role("button", name="Positions").click()
    expect(page.locator(".coach-card", has_text=MARK)).to_have_count(0)
    expect(page.locator(".coach-card .item-title", has_text=re.compile("^Setter$"))).to_be_visible()


@step("Goals: a new goal with why / details, steps, a number and a progress note; done; deleted")
def goals(page):
    go(page, "Goals")
    page.get_by_role("button", name="+ New goal").first.click()
    page.get_by_label("What's the goal?").fill(f"Finish three kits {MARK}")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_label("Goal", exact=True)).to_have_value(f"Finish three kits {MARK}")
    expect(page.get_by_label("When")).to_have_value(re.compile(r"^year:\d{4}$"))           # new goals: this year's
    expect(page.locator(".goal-top .goal-due")).to_contain_text(re.compile("31 Dec|Due in|Due today"))   # aims for 31 December
    page.get_by_label("Why it matters").fill("The stash keeps growing.")
    page.get_by_label("Details").click()                             # leaving a box saves it
    page.get_by_label("Details").fill("One a month. Zero first.")
    page.get_by_label("New step").fill("Finish the Zero")
    page.get_by_label("New step").press("Enter")
    page.get_by_label("New step").fill("Prime the Sherman")
    page.get_by_label("New step").press("Enter")
    expect(page.locator(".goal-steps li")).to_have_count(2)
    page.get_by_label("Done: Finish the Zero").check()
    expect(page.locator(".goal-big-percent")).to_have_text("50%")
    page.get_by_role("button", name="Track a number").click()
    page.get_by_label("Counting").fill("kits")
    page.get_by_label("Target").fill("3")
    page.get_by_label("Progress note").fill("Zero done, decals went on well")
    page.get_by_label("Number now").fill("1")
    page.get_by_role("button", name="Add note").click()
    expect(page.locator(".goal-notes li")).to_contain_text("1 kits · Zero done")
    expect(page.locator(".goal-big-percent")).to_have_text("33%")            # the number wins over the steps
    shot(page, "d60_goal", full=True)
    page.get_by_role("group", name="Status").get_by_role("button", name="Done").click()
    expect(page.locator(".goal-top .goal-due")).to_contain_text("Reached")
    page.get_by_role("link", name="‹ All goals").click()
    page.locator(".chip-filter", has_text="Done").click()
    tile = page.locator(".goal-tile", has_text=MARK)
    expect(page.locator(".goal-section", has=tile).locator(".goal-section-title")).to_contain_text(re.compile(r"\d{4} goals"))
    expect(tile).to_contain_text("1 of 3 kits")
    expect(tile).to_contain_text("The stash keeps growing.")
    # In the feed (Home shows only the latest few: in the morning, a run's date-only items - filed at midday - fill it)
    feed = page.request.get(f"{BASE}/api/activity?limit=200").json()
    assert any(a["kind"] == "goal" and a["title"] == f"Finish three kits {MARK}" for a in feed), "the goal isn't in the feed"
    tile_goal = page.request.get(f"{BASE}/api/goals?status=done").json()["goals"]
    goal_id = next(g["goal_id"] for g in tile_goal if MARK in g["title"])
    page.goto(f"{BASE}/goals/{goal_id}")
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Delete goal").click()
    expect(page).to_have_url(re.compile(r"/goals$"))
    expect(page.locator(".goal-tile", has_text=MARK)).to_have_count(0)


def gpx_file(name):
    """A made-up AllTrails-style recording that ended an hour ago: 3 km due north, climbing 300 m, a minute
    per 100 m, with a lookout waypoint."""
    start = time.time() - 3 * 3600
    stamp = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start + s))
    pts = "".join(f'<trkpt lat="{-27.5 + i * 0.0009:.6f}" lon="153.0"><ele>{100 + i * 10}</ele><time>{stamp(i * 60)}</time></trkpt>'
                  for i in range(31))
    return (f'<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="AllTrails" xmlns="http://www.topografix.com/GPX/1/1">'
            f'<metadata><name>{name}</name><link href="https://www.alltrails.com/trail/australia/example/ridge"><text>AllTrails</text>'
            f'</link></metadata><wpt lat="-27.4865" lon="153.0"><ele>250</ele><name>Lookout</name></wpt>'
            f'<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>').encode()


BLANK_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


def with_gps(jpeg, lat, lon, taken="2026:09:06 07:05:00"):
    """A JPEG with an EXIF block saying where (GPS) and when it was taken, like a phone writes."""
    def dms(v):
        d, rest = int(abs(v)), (abs(v) - int(abs(v))) * 60
        return struct.pack(">6I", d, 1, int(rest), 1, round((rest - int(rest)) * 600), 10)
    ifd0 = struct.pack(">H", 2) + struct.pack(">HHII", 0x8769, 4, 1, 38) + struct.pack(">HHII", 0x8825, 4, 1, 76) + b"\0" * 4
    exif = struct.pack(">H", 1) + struct.pack(">HHII", 0x9003, 2, 20, 56) + b"\0" * 4 + taken.encode() + b"\0"
    gps = (struct.pack(">H", 4) + struct.pack(">HHI", 1, 2, 2) + (b"S" if lat < 0 else b"N") + b"\0\0\0"
           + struct.pack(">HHII", 2, 5, 3, 130) + struct.pack(">HHI", 3, 2, 2) + (b"E" if lon >= 0 else b"W") + b"\0\0\0"
           + struct.pack(">HHII", 4, 5, 3, 154) + b"\0" * 4 + dms(lat) + dms(lon))
    tiff = b"MM\0\x2a" + struct.pack(">I", 8) + ifd0 + exif + gps
    assert len(b"MM\0\x2a\0\0\0\x08" + ifd0) == 38 and len(b"x" * 8 + ifd0 + exif) == 76
    app1 = b"\xff\xe1" + struct.pack(">H", len(tiff) + 8) + b"Exif\0\0" + tiff
    return jpeg[:2] + app1 + jpeg[2:]


@step("Hiking: import an AllTrails GPX (numbers, map, profile, splits), a photo pinned by its GPS, edit, again = skipped, dashboard, Home")
def hiking(page):
    name = f"Ridge loop {MARK}"
    raw = gpx_file(name)
    upload = {"name": "Ridge_loop.gpx", "mimeType": "application/gpx+xml", "buffer": raw}
    # The map's pictures (tiles) are a blank square here: the walk-through doesn't load real ones every run.
    page.route(re.compile(r"https://([a-c]\.tile\.opentopomap\.org|server\.arcgisonline\.com)/.*"),
               lambda route: route.fulfill(status=200, content_type="image/png", body=BLANK_PNG))
    page.goto(BASE + "/hiking/dashboard")
    page.locator(".gpx-import input[type=file]").first.set_input_files(files=[upload])
    d = drawer(page)
    expect(d.get_by_role("heading", name=name)).to_be_visible()             # one file: its hike opens
    numbers = d.locator(".hike-numbers")
    expect(numbers).to_contain_text("3.0 km")
    expect(numbers).to_contain_text("↑ 300 m")
    expect(numbers).to_contain_text("30 min")
    expect(numbers).to_contain_text("10:00 /km")
    expect(d.locator(".hike-map-box .leaflet-overlay-pane path")).to_have_count(5)     # route (+ its edge), start, finish, waypoint
    expect(d.locator(".hike-map-box img.leaflet-tile").first).to_be_attached()
    expect(d.locator(".hike-map-box .leaflet-control-attribution")).to_contain_text("OpenTopoMap")
    expect(d.locator(".hike-pills")).to_contain_text("From GPX")
    d.locator(".hike-profile-svg").hover()
    expect(d.locator(".hike-profile-tip")).to_contain_text(" m")
    expect(d.locator(".hike-map-box .leaflet-overlay-pane path")).to_have_count(6)     # + the hovered point
    page.mouse.move(0, 0)
    d.get_by_role("button", name="Satellite").click()
    expect(d.locator(".hike-map-box .leaflet-control-attribution")).to_contain_text("Esri")
    expect(d.locator(".hike-map-box .hike-tiles-satellite")).to_have_count(1)
    d.get_by_role("button", name="Topo").click()
    # A photo from a phone, taken half a kilometre in: its GPS puts it on the map and the profile.
    jpeg = base64.b64decode(page.evaluate("""() => { const c = document.createElement('canvas'); c.width = 64; c.height = 48;
        const g = c.getContext('2d'); g.fillStyle = '#3a7'; g.fillRect(0, 0, 64, 48); return c.toDataURL('image/jpeg').split(',')[1] }"""))
    photo = {"name": "PXL_20260906.jpg", "mimeType": "image/jpeg", "buffer": with_gps(jpeg, -27.5 + 5 * 0.0009, 153.0)}
    d.locator('input[type=file][data-source="gallery"]').set_input_files(files=[photo])
    expect(d.locator(".hike-gallery-item")).to_have_count(1)
    expect(d.locator(".hike-gallery-item")).to_contain_text("0.5 km")
    expect(d.locator(".hike-map-box .hike-photo-pin")).to_have_count(1)
    expect(d.locator(".hike-profile .hike-mark.photo")).to_have_count(1)
    d.locator(".hike-gallery-item").click()
    viewer = page.get_by_role("dialog", name="Photo")
    expect(viewer).to_contain_text("0.5 km along the track")
    viewer.get_by_label("Caption").fill("First lookout")
    viewer.get_by_label("Caption").press("Tab")
    expect(d.locator(".hike-gallery-item")).to_contain_text("First lookout")
    viewer.press("Escape")                                                    # closes the photo, not the hike
    expect(viewer).to_have_count(0)
    expect(d.get_by_role("heading", name=name)).to_be_visible()
    d.locator("summary", has_text="Splits").click()
    expect(d.locator(".hike-splits tbody tr")).to_have_count(3)
    expect(d.get_by_role("link", name="On AllTrails ↗")).to_have_attribute("href", re.compile("alltrails.com"))
    d.get_by_role("button", name="Edit details").click()
    d.get_by_label("Your rating").select_option("5")
    d.get_by_label("Who with").fill("Sam")
    d.get_by_label("Difficulty").select_option("Hard")
    d.get_by_role("button", name="Save", exact=True).click()
    expect(d.locator(".hike-facts")).to_contain_text("Sam")
    expect(d.locator(".hike-pills")).to_contain_text("Hard")
    shot(page, "d70_hike", full=True)
    page.keyboard.press("Escape")
    # Gear: boots on Hiking → Gear, ticked on the hike; they then count its kilometres.
    page.locator(".sidebar").get_by_role("link", name="Hiking", exact=True).click()
    page.locator(".section-tabs").get_by_role("link", name="Gear", exact=True).click()
    page.get_by_role("button", name="+ Add gear").first.click()
    expect(d.locator("#gear-kinds option[value='Backpack']")).to_have_count(1)        # hiking's kinds, not volleyball's
    expect(d.get_by_text("Find it at Blue Sky Athletics")).to_have_count(0)            # the court-sports shop is volleyball's
    d.get_by_label("Name").fill(f"Boots {MARK}")
    d.get_by_label("Kind").fill("Boots")
    d.get_by_role("button", name="Add gear").click()
    expect(page.locator(".model-card", has_text=f"Boots {MARK}")).to_be_visible()
    page.locator(".section-tabs").get_by_role("link", name="Hikes", exact=True).click()
    page.locator(".hike-list .row-button", has_text=name).click()
    d.get_by_role("button", name="Choose gear").click()
    d.get_by_label(re.compile(f"Boots {MARK}")).check()
    d.get_by_role("button", name="Save gear").click()
    expect(d.locator(".hike-gear-chips")).to_contain_text(f"Boots {MARK}")
    page.keyboard.press("Escape")
    page.locator(".section-tabs").get_by_role("link", name="Gear", exact=True).click()
    boots = page.locator(".model-card", has_text=f"Boots {MARK}")
    expect(boots).to_contain_text("1 hike · 3.0 km")
    boots.click()
    d.get_by_role("button", name="Delete", exact=True).click()
    d.locator(".confirm button.danger").click()                                # "Delete it?" - Delete
    expect(page.locator(".model-card", has_text=f"Boots {MARK}")).to_have_count(0)
    page.goto(BASE + "/hiking/dashboard")
    page.locator(".gpx-import input[type=file]").first.set_input_files(files=[upload])    # the same file again
    expect(d.get_by_role("heading", name=name)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".gpx-results")).to_contain_text("Already imported")
    hikes_now = page.request.get(f"{BASE}/api/hiking/summary").json()["this_year"]["hikes"]
    expect(page.locator(".home-stat", has_text="Hikes in")).to_contain_text(str(hikes_now))
    expect(page.locator(".hike-bests li").first).to_be_visible()
    shot(page, "d71_hiking_dashboard", full=True)
    go(page, "Home")
    expect(page.locator(".home-stat", has_text="Hiked in")).to_contain_text(" km")
    feed = page.request.get(f"{BASE}/api/activity?limit=100").json()          # Home shows only the latest few
    assert any(a["kind"] == "hike" and a["title"] == name and a["verb"] == "Hiked" for a in feed), "no Hiked in the feed"
    page.locator(".sidebar").get_by_role("link", name="Hiking", exact=True).click()
    page.locator(".section-tabs").get_by_role("link", name="Hikes", exact=True).click()
    page.locator(".hike-list .row-button", has_text=name).click()
    page.once("dialog", lambda dlg: dlg.accept())
    d.get_by_role("button", name="Remove").click()
    expect(d).to_have_count(0)
    expect(page.locator(".hike-list .row-button", has_text=name)).to_have_count(0)


@step("Gardening: a balcony to scale, a trough placed and dragged, basil from the guide (too little sun), watered, a harvest with a photo, Today, timeline, harvests, guide, supplies, sowing from a packet")
def gardening(page):
    page.goto(BASE + "/gardening/layout")
    page.get_by_role("button", name=re.compile(r"^\+ (Add a space|Space)$")).first.click()     # the first space, or another
    d = drawer(page)
    d.get_by_label("Name").fill(f"Balcony {MARK}")
    d.get_by_label("Width (cm)").fill("300")
    d.get_by_label("Depth (cm)").fill("120")
    d.get_by_label("That side faces").select_option("N")
    d.get_by_label("Hours of direct sun").fill("3")
    d.get_by_label("Covered (rain doesn't reach it)?").select_option("false")
    d.get_by_role("button", name="Add space").click()
    expect(d).to_have_count(0)
    page.locator(".chip-filter", has_text=f"Balcony {MARK}").click()
    expect(page.locator(".garden-open-side")).to_contain_text("faces north")
    expect(page.locator(".garden-compass")).to_have_count(1)
    page.get_by_role("button", name="+ Container").click()
    d.get_by_label("Name").fill(f"Trough {MARK}")
    d.get_by_label("Kind").select_option("Trough")                         # a trough: 80 x 25 cm, 30 L
    expect(d.get_by_label("Width (cm)")).to_have_value("80")
    d.get_by_role("button", name="Add container").click()
    expect(d.get_by_role("heading", name=f"Trough {MARK}")).to_be_visible()  # opens it
    d.get_by_role("button", name="+ Plant here").click()
    basil = next(g for g in page.request.get(f"{BASE}/api/garden/guides?q=Basil").json()["guides"] if g["name"] == "Basil")
    d.get_by_label("Plant (from the guide)").select_option(str(basil["guide_id"]))
    expect(d.get_by_label("Water every (days)")).to_have_value("2")         # from the guide
    d.get_by_label("Started from").select_option("Seedling")
    d.get_by_role("button", name="Add plant").click()
    expect(d.get_by_role("heading", name=re.compile("Basil"))).to_be_visible()
    expect(d.locator(".alert.low")).to_contain_text("5 h of sun")           # the balcony gets 3
    d.get_by_role("button", name="💧 Watered").click()
    expect(d.locator(".garden-facts")).to_contain_text("next in 2 days")
    d.get_by_label("What").select_option("Harvested")
    d.get_by_label("How much").fill("25")
    d.locator(".garden-log-form textarea").fill("First pesto")
    jpeg = base64.b64decode(page.evaluate("""() => { const c = document.createElement('canvas'); c.width = 80; c.height = 60;
        const g = c.getContext('2d'); g.fillStyle = '#2a7'; g.fillRect(0, 0, 80, 60); return c.toDataURL('image/jpeg').split(',')[1] }"""))
    d.locator('.garden-log-form input[type=file][data-source="gallery"]').set_input_files(
        files=[{"name": "basil.jpg", "mimeType": "image/jpeg", "buffer": jpeg}])
    expect(d.locator(".garden-pending img")).to_have_count(1)
    d.get_by_role("button", name="Save note").click()
    expect(d.locator(".garden-logs")).to_contain_text("25 g")
    expect(d.locator(".garden-log-photos img")).to_have_count(1)
    expect(d.locator(".garden-where .pill")).to_have_text("Harvesting")      # a harvest moves it on
    d.locator(".garden-log-photos button").click()
    viewer = page.get_by_role("dialog", name="Photo")
    expect(viewer).to_contain_text("First pesto")
    viewer.press("Escape")                                                 # closes the photo, not the plant
    expect(viewer).to_have_count(0)
    expect(d.get_by_role("heading", name=re.compile("Basil"))).to_be_visible()
    shot(page, "d80_garden_plant", full=True)
    page.keyboard.press("Escape")
    pot = page.locator(".garden-pot", has_text=f"Trough {MARK}")
    expect(pot).to_contain_text("🌿")
    box = pot.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 120, box["y"] + box["height"] / 2 + 40, steps=6)
    page.mouse.up()
    space_id = next(s["space_id"] for s in page.request.get(f"{BASE}/api/garden/spaces").json() if s["name"] == f"Balcony {MARK}")
    moved = lambda: page.request.get(f"{BASE}/api/garden/spaces/{space_id}").json()["containers"][0]["x_cm"]  # noqa: E731
    for _ in range(20):
        if moved() > 10:
            break
        time.sleep(0.2)
    assert moved() > 10, "the trough didn't move"
    expect(drawer(page)).to_have_count(0)                                  # a drag isn't a tap
    pot.click()                                                            # a tap opens it; two the same: Copy
    drawer(page).get_by_role("button", name="Copy", exact=True).click()
    expect(drawer(page).get_by_role("heading", name=f"Trough {MARK} 2")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".garden-pot")).to_have_count(2)
    shot(page, "d81_garden_layout", full=True)
    page.locator(".section-tabs").get_by_role("link", name="Today", exact=True).click()
    expect(page.locator(".home-card", has_text="Sow in")).to_be_visible()
    expect(page.locator(".garden-photo-strip img").first).to_be_visible()
    shot(page, "d82_garden_today", full=True)
    page.locator(".section-tabs").get_by_role("link", name="Plants", exact=True).click()
    expect(page.locator(".garden-group", has_text=f"Balcony {MARK}")).to_contain_text("Basil")
    page.get_by_role("button", name="Timeline").click()
    expect(page.locator(".garden-timeline-bar").first).to_be_visible()
    # Bought, not planted yet: a grown plant you have (Supplies) shows in Plants until it's planted
    petunia = page.request.post(f"{BASE}/api/garden/items", data={"name": f"Petunia {MARK}", "kind": "Plant", "status": "Have"}).json()
    page.goto(BASE + "/gardening/plants")                                  # (added behind its back: load it again)
    waiting = page.locator(".garden-bought", has_text=f"Petunia {MARK}")
    waiting.get_by_role("button", name="Add to my plants").click()
    expect(drawer(page).get_by_role("heading", name=re.compile(f"Petunia {MARK}"))).to_be_visible()
    page.keyboard.press("Escape")
    expect(waiting).to_have_count(0)
    expect(page.locator(".garden-group", has_text="Not in a pot yet")).to_contain_text(f"Petunia {MARK}")
    for p in page.request.get(f"{BASE}/api/garden/plantings?q=Petunia {MARK}").json():
        page.request.delete(f"{BASE}/api/garden/plantings/{p['planting_id']}")
    page.request.delete(f"{BASE}/api/garden/items/{petunia['item_id']}")
    # The plant doctor: from the basil, "Something wrong?"; pick what you see; "I've got this" notes it and sets a reminder
    page.locator(".garden-group", has_text=f"Balcony {MARK}").get_by_text("Basil").first.click()
    drawer(page).get_by_role("button", name="Something wrong?").click()
    expect(page).to_have_url(re.compile(r"/gardening/doctor\?plant=\d+"))
    page.get_by_role("button", name="Sticky", exact=True).click()
    page.get_by_role("button", name="Tiny bugs on new growth", exact=True).click()
    first = page.locator(".garden-doc-list > li").first
    expect(first).to_contain_text("Aphids")
    first.locator(".garden-doc-head").click()
    expect(first).to_contain_text("What to do")
    first.get_by_role("button", name=re.compile("^I've got this")).click()
    expect(first).to_contain_text("Noted")
    basil_id = int(re.search(r"plant=(\d+)", page.url).group(1))
    assert any(t["planting_id"] == basil_id and "aphids" in t["title"] for t in page.request.get(f"{BASE}/api/garden/tasks").json())
    shot(page, "d83_garden_doctor", full=True)
    page.locator(".section-tabs").get_by_role("link", name="Harvests", exact=True).click()
    expect(page.locator(".home-card", has_text="Every harvest")).to_contain_text("Basil")
    page.locator(".section-tabs").get_by_role("link", name="Guide", exact=True).click()
    page.get_by_role("button", name="All", exact=True).click()
    page.locator(".garden-guide-card", has_text="Cherry tomato").click()
    expect(d.get_by_role("button", name="Make my own copy")).to_be_visible()
    expect(d.locator(".sow-months").first).to_be_visible()
    page.keyboard.press("Escape")
    page.locator(".section-tabs").get_by_role("link", name="Supplies", exact=True).click()
    page.get_by_label("Bunnings link - or words to search Bunnings for").fill("potting mix")
    expect(page.get_by_role("button", name="Search Bunnings ↗")).to_be_visible()   # words: opens their search (not clicked here)
    page.get_by_label("Bunnings link - or words to search Bunnings for").fill("https://www.bunnings.com.au/x-mix_p1234567")
    expect(page.get_by_role("button", name="Add from Bunnings")).to_be_visible()    # a link: read that page (not clicked: no live read)
    page.get_by_role("button", name="+ Add by hand").click()
    d.get_by_label(re.compile(r"^Name")).fill(f"Basil seeds {MARK}")     # (the plant list's options mention "name" too)
    d.get_by_label("Which plant").select_option(str(basil["guide_id"]))
    d.get_by_label("Packets").fill("2")
    d.get_by_role("button", name="Add", exact=True).click()
    expect(d.get_by_role("heading", name=f"Basil seeds {MARK}")).to_be_visible()
    d.get_by_role("button", name="Sow", exact=True).click()
    expect(d.get_by_role("heading", name=re.compile("Basil"))).to_be_visible()      # the new planting opens
    expect(d.locator(".garden-where .pill")).to_have_text("Sown")
    page.keyboard.press("Escape")
    # tidy up through the API (the steps above went through the screens)
    for p in page.request.get(f"{BASE}/api/garden/plantings?status=all&q=Basil").json():
        if p["space_name"] == f"Balcony {MARK}" or p["container_name"] is None:
            page.request.delete(f"{BASE}/api/garden/plantings/{p['planting_id']}")
    for i in page.request.get(f"{BASE}/api/garden/items").json():
        if MARK in i["name"]:
            page.request.delete(f"{BASE}/api/garden/items/{i['item_id']}")
    for c in page.request.get(f"{BASE}/api/garden/spaces/{space_id}").json()["containers"]:
        page.request.delete(f"{BASE}/api/garden/containers/{c['container_id']}")
    page.request.delete(f"{BASE}/api/garden/spaces/{space_id}")


FAKE_BUNNINGS = """<html><head><title>Leek - Bunnings</title></head><body><h1>100mm Leek</h1>
<script id="__NEXT_DATA__" type="application/json">%s</script></body></html>""" % json.dumps({"props": {"pageProps": {
    "initialState": {"global": {"userData": {"appliedStore": {"name": "4123", "displayName": "Stafford"}}}},
    "dehydratedState": {"queries": [
        {"queryKey": ["product-retail-price", "0999901", "4123"], "state": {"data": {"priceAvailable": True, "value": 4.98}}},
        {"queryKey": ["product-aisle-item-location", "0999901", "4123"], "state": {"data": [{"inStoreLocations": [
            {"aisle": "35", "bay": "8", "sequence": "69"}]}]}},
        {"queryKey": ["product-fulfilment", "0999901", "4123"], "state": {"data": {"availableInStore": True,
            "inStorePickUpData": {"inStoreStockColor": "GREEN", "inStoreStockMsg": "inStock"}}}},
        {"queryKey": ["retail-product", "0999901", "4123"], "state": {"data": {"name": "100mm Test Leek", "itemNumber": "0999901",
            "manufacturer": "Garden Express", "allCategories": [{"displayName": "Garden"}, {"displayName": "Vegetable Plants"}],
            "images": [{"imageType": "PRIMARY", "url": "https://media.bunnings.com.au/api/public/content/leek?v=1"}]}}}]}}}})


@step("Travel: plan a trip (overseas), a to-do, a flight, money in yen (stand-in rates), a packing list ticked, a place found and on the map; trips, places and packing pages")
def travel(page):
    from datetime import date, timedelta
    start, end = date.today() + timedelta(days=10), date.today() + timedelta(days=14)
    page.goto(BASE + "/travel/dashboard")
    page.get_by_role("button", name="+ Plan a trip").first.click()
    d = drawer(page)
    d.get_by_label(re.compile(r"^Name")).fill(f"Trip {MARK}")
    d.get_by_label(re.compile(r"^Kind")).select_option("Overseas")
    d.get_by_label("From", exact=True).fill(start.isoformat())
    d.get_by_label("To", exact=True).fill(end.isoformat())
    d.get_by_label(re.compile(r"^Countries")).fill("Japan")
    d.get_by_role("button", name="Plan it").click()
    expect(d.get_by_role("heading", name=f"Trip {MARK}")).to_be_visible()     # opens it
    expect(d.locator(".section-head").first).to_contain_text("In 10 days")
    expect(d).to_contain_text("Japan")
    # Plan: something to do before you go
    d.get_by_label("Add to the plan").fill("Apply for the visa")
    d.get_by_role("button", name="Add", exact=True).click()
    expect(d.locator(".trip-checklist")).to_contain_text("Apply for the visa")
    # A booking (its own panel, then back to the trip)
    d.get_by_role("tab", name="Bookings").click()
    d.get_by_role("button", name="+ Add a booking").click()
    d.get_by_label(re.compile(r"^What")).fill("QF61")
    d.get_by_label("Cost", exact=True).fill("1200")
    d.get_by_role("button", name="Add booking").click()
    expect(d.locator(".trip-bookings")).to_contain_text("QF61")
    expect(d.locator(".trip-bookings")).to_contain_text("To pay")
    # Money: ramen in yen, in AUD at the (stand-in) rate: 100 yen to the dollar
    d.get_by_role("tab", name="Money").click()
    d.get_by_label("Amount").fill("2500")
    d.get_by_label("Currency", exact=True).select_option("JPY")
    d.get_by_label("What", exact=True).fill("Ramen")
    d.get_by_role("button", name="Add", exact=True).click()
    expect(d.locator(".trip-expenses")).to_contain_text("Ramen")
    expect(d.locator(".trip-expenses")).to_contain_text("$25.00")
    expect(d.locator(".trip-money")).to_contain_text("$1,225.00")
    shot(page, "e10_trip_money", full=False)
    # Packing: the Overseas list, the passport ticked
    d.get_by_role("tab", name=re.compile(r"^Packing")).click()
    lists = d.get_by_label("A packing list")
    lists.select_option(label=next(o for o in lists.locator("option").all_inner_texts() if o.startswith("Overseas")))
    d.get_by_role("button", name="Add list").click()
    expect(d.get_by_label("Passport", exact=True)).to_be_visible()
    d.get_by_label("Passport", exact=True).click()                         # ticked once saved
    expect(d.get_by_label("Passport", exact=True)).to_be_checked()
    expect(d.get_by_role("tab", name=re.compile(r"^Packing"))).to_contain_text("1/")
    # Places: found by name (Open-Meteo's place search - a stand-in), then on the trip's map
    d.get_by_role("tab", name="Places").click()
    d.get_by_role("button", name="+ Add a place").click()
    d.get_by_label("Find a town or city").fill("Brisbane")
    d.get_by_role("button", name="Find", exact=True).click()
    d.locator(".travel-found button", has_text="Brisbane").click()
    expect(d.get_by_label(re.compile(r"^Latitude"))).to_have_value("-27.47")
    d.get_by_role("button", name="Add place").click()
    expect(d.locator(".trip-stops")).to_contain_text("Brisbane")
    expect(d.locator(".travel-map-box")).to_be_visible()
    shot(page, "e11_trip_places", full=False)
    page.keyboard.press("Escape")
    # The pages: every trip, places (the map), packing lists
    page.goto(BASE + "/travel/trips")
    expect(page.locator(".trip-group", has_text="Coming up")).to_contain_text(f"Trip {MARK}")
    page.goto(BASE + "/travel/places")
    expect(page.locator(".travel-map-box")).to_be_visible()
    expect(page.locator(".home-card", has_text="Places")).to_contain_text("Brisbane")
    page.goto(BASE + "/travel/packing")
    expect(page.locator(".packing-list-fold", has_text="Essentials")).to_be_visible()
    page.goto(BASE + "/travel/dashboard")
    expect(page.locator(".home-card", has_text="Coming up")).to_contain_text(f"Trip {MARK}")
    shot(page, "e12_travel_dashboard", full=False)
    for trip in json.load(urllib.request.urlopen(f"{BASE}/api/travel/trips")):
        if trip["name"] == f"Trip {MARK}":
            page.request.delete(f"{BASE}/api/travel/trips/{trip['trip_id']}")


@step("Precision shooting: a rifle (MIL scope) and ammo, a session with a group (MOA / MIL, what to dial), shots plotted, a photo, the live board (hit / miss), DOPE card, dashboard")
def shooting(page):
    page.goto(BASE + "/shooting/rifles")
    page.get_by_role("button", name="+ Add a rifle").first.click()
    d = drawer(page)
    d.get_by_label(re.compile(r"^Name")).fill(f"Rifle {MARK}")
    d.get_by_label(re.compile(r"^Kind")).select_option("Rimfire")
    d.get_by_label("Scope turrets").select_option("MIL")
    d.get_by_role("button", name="Add rifle").click()
    expect(d.get_by_role("heading", name=f"Rifle {MARK}")).to_be_visible()     # opens it
    expect(d).to_contain_text("0.1 a click")                                   # MIL turrets: 0.1 a click
    page.keyboard.press("Escape")
    page.goto(BASE + "/shooting/ammo")
    page.get_by_role("button", name="+ Add ammo").first.click()
    d.get_by_label(re.compile(r"^Name")).fill(f"Ammo {MARK}")
    d.get_by_label("Rounds in a box").fill("50")
    d.get_by_label("Price a box").fill("12.50")
    d.get_by_label("Rounds bought (all up)").fill("500")
    d.get_by_role("button", name="Add ammo").click()
    expect(d).to_contain_text("$0.25 a round")
    page.keyboard.press("Escape")
    # a session: the rifle and ammo picked, then a group - its size in MOA / MIL as you type, what to dial
    page.goto(BASE + "/shooting/sessions")
    page.get_by_role("button", name="+ Log a session").first.click()
    d.get_by_label(re.compile(r"^Rifle")).select_option(label=f"Rifle {MARK}")   # (a select's label holds its options too)
    d.get_by_label(re.compile(r"^Ammo")).select_option(label=f"Ammo {MARK}")
    d.get_by_role("button", name="Start logging").click()
    d.get_by_role("button", name="+ Add a group").click()
    form = d.get_by_role("form", name="New group")
    form.get_by_label("Distance", exact=True).fill("50")
    form.get_by_label("Shots", exact=True).fill("5")
    form.get_by_label("Group size (mm)").fill("10")
    expect(form.locator(".shoot-live")).to_contain_text("0.69 MOA · 0.20 MIL")
    form.get_by_label("Hit high by (mm)").fill("15")
    form.get_by_label("Elevation dialled (MIL)").fill("0.5")
    form.get_by_label("Chronograph speeds (m/s)").fill("325 328 326")
    form.get_by_label("This confirms my elevation at this distance (DOPE)").check()
    form.get_by_role("button", name="Add and plot shots").click()     # saves it and opens its target, ready to tap
    group = d.locator(".shoot-group").first
    expect(group).to_contain_text("0.69 MOA")
    expect(group).to_contain_text("Dial 0.30 MIL down (3 clicks)")
    expect(group).to_contain_text("SD 1.5")
    # shot by shot: tap three shots onto the target; the group's size and centre then come from them
    expect(group.get_by_role("button", name="Done plotting")).to_be_visible()
    box = group.locator(".shoot-plot svg").bounding_box()
    for dx, dy in ((0.52, 0.48), (0.56, 0.47), (0.54, 0.53)):
        n = group.locator(".shoot-plot-shot").count()
        page.mouse.click(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy)
        expect(group.locator(".shoot-plot-shot")).to_have_count(n + 1)
    group.get_by_role("button", name="Done plotting").click()
    expect(group).to_contain_text("50 m · 3 shots")
    expect(group).to_contain_text("Mean radius")
    expect(group.locator(".shoot-shot-table tbody tr")).to_have_count(3)
    # a photo of the session (a made-up JPEG)
    jpeg = base64.b64decode(page.evaluate("""() => { const c = document.createElement('canvas'); c.width = 80; c.height = 60;
        const g = c.getContext('2d'); g.fillStyle = '#c33'; g.fillRect(0, 0, 80, 60); return c.toDataURL('image/jpeg').split(',')[1] }"""))
    d.get_by_role("region", name="Photos and video").locator('input[type=file][data-source="gallery"]').set_input_files(files=[{"name": "target.jpg", "mimeType": "image/jpeg", "buffer": jpeg}])
    expect(d.locator(".shoot-media img")).to_have_count(1)
    shot(page, "d90_shooting_session", full=True)
    page.keyboard.press("Escape")
    rifle_id = next(r["rifle_id"] for r in page.request.get(f"{BASE}/api/shooting/rifles").json() if r["name"] == f"Rifle {MARK}")
    page.goto(f"{BASE}/shooting/dope?rifle={rifle_id}")
    expect(page.locator(".shoot-dope tbody tr").first).to_contain_text("0.5 MIL")
    expect(page.locator(".shoot-dope tbody tr").first).to_contain_text("Confirmed")
    # the live board: hit, miss, hit, hit, hit - counting as it goes - then wrap the group up
    page.goto(BASE + "/shooting/sessions")
    page.get_by_role("button", name="Start shooting").click()                  # today's session: opens its live board
    board = page.get_by_role("dialog", name="Live board")
    board.get_by_label("Distance", exact=True).fill("300")
    board.get_by_label("Target").fill("2 MOA steel")
    board.get_by_role("button", name="Start").click()
    for b in ("HIT", "MISS", "HIT", "HIT", "HIT"):
        board.get_by_role("button", name=b, exact=True).click()
    counts = board.locator(".shoot-board-counts")
    expect(counts).to_contain_text("5shots")
    expect(counts).to_contain_text("4hits")
    expect(counts).to_contain_text("80%")
    expect(board).to_contain_text("3 in a row")
    board.get_by_role("button", name="HIT", exact=True).click()
    board.get_by_role("button", name="Undo").click()                           # takes the last one back
    expect(counts).to_contain_text("5shots")
    shot(page, "d92_shooting_live", full=False)
    board.get_by_role("button", name="Finish group").last.click()
    expect(board.locator(".shoot-board-result")).to_contain_text("4/5")
    # ...or the target: tap where each shot landed; the group, mean radius and what to dial work out as you go
    board.get_by_role("button", name="Change distance").click()
    board.get_by_role("button", name="Target", exact=True).click()
    board.get_by_label("Distance", exact=True).fill("50")
    board.get_by_label("Target", exact=True).fill("")
    board.get_by_role("button", name="Start").click()
    face = board.locator(".shoot-board-target svg")
    box = face.bounding_box()
    for dx, dy in ((0.53, 0.47), (0.58, 0.45), (0.55, 0.52)):
        page.mouse.click(box["x"] + box["width"] * dx, box["y"] + box["height"] * dy)
    counts = board.locator(".shoot-board-counts")
    expect(counts).to_contain_text("3shots")
    expect(counts).to_contain_text("MIL")                                       # the rifle's scope unit
    expect(board.locator(".shoot-board-streak")).to_contain_text("Dial")
    board.get_by_role("button", name="Off target").click()
    expect(counts).to_contain_text("1off target")
    board.get_by_role("button", name="Undo").click()
    expect(counts).to_contain_text("0off target")
    shot(page, "d93_shooting_live_target", full=False)
    board.get_by_role("button", name="Finish group").last.click()
    expect(board.locator(".shoot-board-result")).to_contain_text("3 shots")
    board.get_by_role("button", name="Done").click()
    expect(drawer(page).locator(".shoot-group", has_text="2 MOA steel")).to_contain_text("4/5 (80%)")
    page.keyboard.press("Escape")
    page.locator(".section-tabs").get_by_role("link", name="Dashboard", exact=True).click()
    expect(page.locator(".home-card", has_text="Best groups")).to_contain_text("50 m")
    expect(page.locator(".home-card", has_text="Hit rate by distance")).to_be_visible()
    shot(page, "d91_shooting_dashboard", full=True)
    assert any(f["kind"] == "shoot" for f in page.request.get(f"{BASE}/api/activity").json())
    # tidy up through the API
    for s in page.request.get(f"{BASE}/api/shooting/sessions?rifle_id={rifle_id}").json():
        page.request.delete(f"{BASE}/api/shooting/sessions/{s['session_id']}")
    page.request.delete(f"{BASE}/api/shooting/rifles/{rifle_id}")
    for a in page.request.get(f"{BASE}/api/shooting/ammo").json():
        if a["name"] == f"Ammo {MARK}":
            page.request.delete(f"{BASE}/api/shooting/ammo/{a['ammo_id']}")


@step("Bunnings button: set up on Supplies; on a (made-up) Bunnings plant page for Stafford it sends the price, stock and aisle; saved")
def bunnings_button(page):
    page.goto(BASE + "/gardening/supplies")
    page.get_by_text("Plants and your store's prices: the Bunnings button").click()
    link = page.get_by_role("link", name="Send to Off the Clock")
    href = link.get_attribute("href")
    assert href.startswith("javascript:"), href[:40]
    script = urllib.parse.unquote(href[len("javascript:"):])
    assert BASE in script                                   # it knows this app's address
    # A Bunnings product page as your browser has it with Stafford chosen (made up, served by the test).
    page.route("https://www.bunnings.com.au/**", lambda route: route.fulfill(status=200, content_type="text/html", body=FAKE_BUNNINGS))
    page.route("https://media.bunnings.com.au/**", lambda route: route.fulfill(status=200, content_type="image/png", body=BLANK_PNG))
    page.goto("https://www.bunnings.com.au/100mm-test-leek_p0999901")
    page.evaluate("window.open = (u) => { window.__sent = u }")          # where the button would go
    page.evaluate(script)
    sent = page.evaluate("window.__sent")
    assert sent and sent.startswith(BASE + "/gardening/supplies#bunnings="), sent
    page.goto(sent)
    card = page.locator(".garden-sent")
    expect(card).to_contain_text("100mm Test Leek")
    expect(card).to_contain_text("in stock at Stafford")
    expect(card).to_contain_text("$4.98")
    expect(card).to_contain_text("Aisle 35, Bay 8 at Stafford")
    card.get_by_label("I", exact=True).select_option("Wanted")
    card.get_by_role("button", name="Save").click()
    d = drawer(page)
    expect(d.get_by_role("heading", name="100mm Test Leek")).to_be_visible()
    expect(d).to_contain_text("In stock at Stafford")
    expect(d).to_contain_text("Aisle 35, Bay 8 at Stafford")
    expect(page).to_have_url(BASE + "/gardening/supplies")                  # the details are gone from the address
    page.keyboard.press("Escape")
    shops = {s["shop"]: s for s in page.request.get(f"{BASE}/api/wanted").json()["shops"]}
    assert any(i["name"] == "100mm Test Leek" for i in shops["Bunnings"]["items"])
    item_id = next(i["item_id"] for i in page.request.get(f"{BASE}/api/garden/items").json() if i["bunnings_item"] == "0999901")
    page.request.delete(f"{BASE}/api/garden/items/{item_id}")
    # Today's weather says what kind of day it is (the stand-in forecast: mostly sunny, then rain).
    was = page.request.get(f"{BASE}/api/garden/settings").json()
    page.request.put(f"{BASE}/api/garden/settings", data={"place_name": "Brisbane", "lat": -27.47, "lon": 153.03})
    page.goto(BASE + "/gardening")
    expect(page.locator(".garden-weather li").first).to_contain_text("Mostly sunny")
    expect(page.locator(".garden-weather li").nth(1)).to_contain_text("Rain")
    page.request.put(f"{BASE}/api/garden/settings", data={k: was[k] for k in ("place_name", "lat", "lon")})


@step("Supplies: a kit's parts - the ones its name says it comes with, added in one go; a part says its kit; searching finds both")
def supply_kit(page):
    lists = page.request.get(f"{BASE}/api/lookups").json()
    tools = next(c["id"] for c in lists["categories"] if c["name"] == "Tools")
    kit = page.request.post(f"{BASE}/api/supplies", data={
        "name": f"Kit {MARK} Includes Nipper, Hobby Knife, Tweezers & Sanding Sticks", "category_id": tools, "qty_on_hand": 1,
        "purchased_from": "Amazon"}).json()
    go(page, "Supplies")
    page.get_by_placeholder("Search name, code, brand, notes, barcode...").fill(f"Kit {MARK}")
    page.locator("tr.row", has_text=f"Kit {MARK}").click()
    d = drawer(page)
    parts = d.get_by_role("region", name="In this kit")
    for name in ("Nipper", "Hobby Knife", "Tweezers", "Sanding Sticks"):
        expect(parts.get_by_label(name)).to_be_checked()
    parts.get_by_label("Tweezers").uncheck()
    parts.get_by_role("button", name="Add 3 parts").click()
    expect(parts.locator(".kit-list li")).to_have_count(3)
    expect(parts.get_by_label("Tweezers")).to_be_visible()                    # still on offer
    parts.get_by_label("Part name").fill("Sanding Stick #400")
    parts.get_by_role("button", name="+ Add a part").click()
    expect(parts.locator(".kit-list li")).to_have_count(4)
    parts.locator(".kit-list li", has_text="Nipper").click()
    expect(d.get_by_role("heading", name="Nipper")).to_be_visible()
    expect(d.locator(".kit-of")).to_contain_text(f"Kit {MARK}")
    page.keyboard.press("Escape")
    page.get_by_placeholder("Search name, code, brand, notes, barcode...").fill("Nipper")
    rows = page.locator("tr.row")
    expect(rows.filter(has_text=f"in Kit {MARK}")).to_have_count(1)            # the nipper, in its kit
    expect(rows.filter(has_text="kit · 4 parts")).to_have_count(1)            # and the kit, which has one
    shot(page, "d40_supply_kit", full=False)
    for s in page.request.get(f"{BASE}/api/supplies/{kit['supply_id']}").json()["parts"]:
        page.request.delete(f"{BASE}/api/supplies/{s['supply_id']}")
    page.request.delete(f"{BASE}/api/supplies/{kit['supply_id']}")


@step("Wishlist by shop: the default shop first, Good Games for board games; gear from Blue Sky (stand-in)")
def wishlist_shops(page):
    game = page.request.post(f"{BASE}/api/board-games", data={"name": f"Wantgame {MARK}", "status": "Wanted"}).json()
    go(page, "Wishlist")
    expect(page.locator(".shop-heading").first).to_contain_text(page.request.get(f"{BASE}/api/settings").json()["default_shop"])
    section = page.locator(".shop-section", has=page.locator(".shop-heading", has_text="Good Games"))
    expect(section.locator(".wanted-card", has_text=f"Wantgame {MARK}")).to_be_visible()
    page.locator(".shop-jump").get_by_role("link", name=re.compile("^Good Games")).click()
    shot(page, "d59_wishlist_shops", full=False)
    page.request.delete(f"{BASE}/api/board-games/{game['game_id']}")
    # Gear you want, found at Blue Sky Athletics (Way of Wade) - its stand-in in this copy (nothing is added here).
    go(page, "Gear")
    page.get_by_role("button", name="+ Want").click()
    d = drawer(page)
    d.get_by_label("Find it at Blue Sky Athletics (Way of Wade)").fill("way of wade")
    expect(d.locator(".shop-results li").first.or_(d.locator(".alert.error"))).to_be_visible(timeout=60000)
    if d.locator(".shop-results li").count():
        expect(d.locator(".shop-results li").first.get_by_role("button", name="Want this")
               .or_(d.locator(".shop-results li").first.locator(".pill", has_text="In your gear"))).to_be_visible()
    else:
        print("    Blue Sky Athletics couldn't be reached - skipped")
    page.keyboard.press("Escape")


@step("Video games Friends: the list (or why it's private) and the add form")
def video_game_friends(page):
    go(page, "Video games")
    page.locator(".section-tabs").get_by_role("link", name="Friends").click()
    # Connected to Steam: friends, or the note that the friends list is private; not connected: an error to connect.
    expect(page.locator(".friend-card").or_(page.locator(".alert", has_text=re.compile("friends list is private|Connect your Steam")))
           .or_(page.locator(".empty-state")).first).to_be_visible(timeout=30000)
    page.get_by_role("button", name="+ Add a friend").first.click()
    expect(page.get_by_label("Friend's Steam profile")).to_be_visible()
    shot(page, "d58_friends", full=False)


@step("Board games: a play of a friend's game; an abandoned play")
def board_game_elsewhere(page):
    go(page, "Board games")
    page.locator(".section-tabs").get_by_role("link", name="Plays").click()
    page.get_by_role("button", name="+ Log a play").first.click()
    d = drawer(page)
    d.get_by_label("Game", exact=True).select_option("elsewhere")
    d.get_by_label("Their game").fill(f"Friendgame {MARK}")
    d.get_by_label("Who won").fill("Sam")
    d.get_by_role("button", name="Save play").click()
    row = page.locator(".list li", has_text=f"Friendgame {MARK}")
    expect(row).to_contain_text("played elsewhere")
    expect(row).to_contain_text("Sam")
    # Abandoned: no winner box, and the play says so.
    page.get_by_role("button", name="+ Log a play").first.click()
    d = drawer(page)
    d.get_by_label("Game", exact=True).select_option(label=f"Friendgame {MARK}")      # now in the list (Played elsewhere)
    d.get_by_role("switch", name="Didn't finish (abandoned)").check()
    expect(d.get_by_label("Who won")).to_have_count(0)
    d.get_by_role("button", name="Save play").click()
    expect(page.locator(".list li", has_text=f"Friendgame {MARK}").locator(".pill", has_text="Abandoned")).to_have_count(1)
    shot(page, "d56_plays_elsewhere", full=False)
    games = page.request.get(f"{BASE}/api/board-games").json()
    friend = next(g for g in games if g["name"] == f"Friendgame {MARK}")
    assert friend["status"] == "Played elsewhere", friend
    page.request.delete(f"{BASE}/api/board-games/{friend['game_id']}")


@step("Board games: game / expansion / other groups and filter; To sell")
def board_game_kinds(page):
    base = page.request.post(f"{BASE}/api/board-games", data={"name": f"Base-{MARK}"}).json()
    page.request.post(f"{BASE}/api/board-games", data={"name": f"Base-{MARK} Big Expansion", "kind": "expansion",
                                                        "base_game_id": base["game_id"]})
    go(page, "Board games")
    groups = page.locator(".game-group summary .fold-title")
    expect(groups.first).to_have_text("Base games")
    expect(page.locator(".model-card", has_text=f"Base-{MARK} Big Expansion")).to_contain_text(f"Expansion for Base-{MARK}")
    page.get_by_role("group", name="Type").get_by_role("button", name=re.compile("^Base games")).click()
    expect(groups).to_have_count(1)
    expect(page.locator(".model-card", has_text=f"Base-{MARK} Big Expansion")).to_have_count(0)
    page.get_by_role("group", name="Type").get_by_role("button", name=re.compile("^All types")).click()
    page.locator(".model-card", has_text=f"Base-{MARK}").first.click()
    d = drawer(page)
    d.get_by_role("group", name="Status").get_by_role("button", name="To sell").click()
    expect(d.get_by_role("group", name="Status").get_by_role("button", name="To sell")).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Escape")


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
    d.locator("summary", has_text="Lookup sites").click()             # the weekly site check (no live run here)
    expect(d.locator(".site-check")).to_have_count(16)
    expect(d.get_by_role("button", name="Check now")).to_be_visible()
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
    drawer(page).get_by_text("Photo options").click()             # a touch screen: camera or gallery
    expect(drawer(page).get_by_role("button", name="Take photo")).to_be_visible()
    expect(drawer(page).get_by_role("button", name="Gallery")).to_be_visible()
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
    expect(page.locator(".hobby-card")).to_have_count(11)         # models, board games, volleyball, video games, chess, reading, car, travel, shooting, hiking, gardening
    car = page.locator(".hobby-card", has_text="Building my car")
    expect(car.locator(".under-construction")).to_be_visible()     # the spanner: still to be built
    fits("Hobbies")
    for hobby, tabs in (("Models", ("Kits", "Colours")), ("Board games", ("Games", "Plays")),
                        ("Volleyball", ("Games", "Gear", "Videos", "Coach")), ("Video games", ("Dashboard", "Games", "Stats", "Friends")),
                        ("Hiking", ("Dashboard", "Hikes", "Gear")),
                        ("Gardening", ("Today", "Layout", "Plants", "Guide", "Harvests", "Supplies"))):   # six tabs: they scroll
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
               models, model_paste, add_model_hasegawa, add_model_trumpeter, undo, add_to_wishlist_button, duplicate_check, wishlist_panel, shop_tamiya, used_up,
               scalemates, desktop_tabs, model_edit, lists_protect, kit_paints, timer, build_log, stash, mixes,
               matches, used_on, gundam, bandai_lookup, warhammer, journal_write, journal_links, journal_from_model,
               journal_suggestion, journal_todo, global_search, journal_wishlist, banners, appearance,
               build_underway, calendar, volleyball, board_games, whiteboard, sketch_block, writing_mode, mood, video_games, chess, reading, warhammer_range, warhammer_minis, gundam_range, board_game_kinds, board_game_elsewhere, volleyball_coach, video_game_friends, wishlist_shops, goals, supply_kit, hiking, gardening, shooting, travel, bunnings_button, settings_more, no_panel):
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
