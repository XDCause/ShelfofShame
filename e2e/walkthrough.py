"""End-to-end walk-through of Shelf of Shame in a real (headless) browser.

Run it with .\\run_e2e.ps1 (backs up first and restores afterwards - this script changes data).
Runs inside the Playwright container on the app's Docker network, against http://web.
Prints a PASS/FAIL line per step, all browser errors, and saves screenshots to /out.
Written against the user's real data (the Zero and P-40E models, XF-1 etc.); item counts are
read from the API at the start, so adding or removing supplies doesn't break it.
"""
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


@step("Manage lists opens from the gear; Spending opens when tapped")
def manage_lists(page):
    page.get_by_role("button", name="Manage lists").click()
    expect(drawer(page)).to_contain_text("Brands")
    shot(page, "d05_manage_lists")
    # Spending is closed until you open it
    spend = drawer(page).locator("details.spending")
    expect(spend.locator(".spend-totals")).to_have_count(0)
    spend.locator("summary").click()
    expect(spend.locator(".spend-totals")).to_contain_text("All time")
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
    page.locator(".toolbar").get_by_role("button", name="Type a barcode").click()
    page.get_by_label("Barcode number").fill("4950344070053")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page)).to_contain_text("XF76", timeout=20000)
    page.keyboard.press("Escape")


@step("Scan by typed barcode: unknown opens Add panel")
def scan_unknown(page):
    page.locator(".toolbar").get_by_role("button", name="Type a barcode").click()
    page.get_by_label("Barcode number").fill("036000291452")
    page.locator(".scan-panel").get_by_role("button", name="Look up").click()
    expect(drawer(page)).to_contain_text("New barcode", timeout=20000)
    shot(page, "d08_scan_unknown")
    page.keyboard.press("Escape")


@step("Models: list and the Zero's checklist")
def models(page):
    page.get_by_role("tab", name="Models").click()
    expect(page.locator(".model-card")).to_have_count(2)
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


@step("Floating Scan button is phone-only")
def fab_desktop(page):
    expect(page.locator(".fab")).to_be_hidden()


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


@step("Manage lists: brand used only by a model can't be removed")
def lists_protect(page):
    page.get_by_role("button", name="Manage lists").click()
    expect(drawer(page).get_by_role("button", name="Remove Hasegawa")).to_be_disabled()
    page.keyboard.press("Escape")


@step("Escape closes panels; no panel left open")
def no_panel(page):
    expect(page.locator("aside.drawer")).to_have_count(0)


# ---------------------------------------------------------------- phone
@step("Phone: inventory, item panel, add panel, wishlist, models")
def phone(page):
    page.goto(BASE)
    expect(page.locator("tr.row").first).to_be_visible(timeout=15000)
    shot(page, "m01_inventory", full=False)
    # Header: gear on the title row, tabs on their own row below
    gear, tabs = page.get_by_role("button", name="Manage lists").bounding_box(), page.locator(".tabs").bounding_box()
    assert gear["y"] < tabs["y"], f"gear y={gear['y']} should be above tabs y={tabs['y']}"
    size = page.get_by_label("Search").evaluate("e => getComputedStyle(e).fontSize")
    assert size == "16px", f"search box font {size} (iPhone zooms in below 16px)"
    expect(page.locator(".fab")).to_be_visible()  # floating Scan button on phones
    page.locator("tr.row").first.click()
    expect(drawer(page)).to_be_visible()
    expect(page.locator(".fab")).to_be_hidden()  # ...but not over an open panel
    page.wait_for_timeout(400)  # let the slide-in finish
    shot(page, "m02_item_panel", full=False)
    page.keyboard.press("Escape")
    page.get_by_role("button", name="+ Add", exact=True).click()
    page.wait_for_timeout(400)
    shot(page, "m03_add_panel", full=False)
    page.keyboard.press("Escape")
    page.get_by_role("tab", name="Wishlist").click()
    shot(page, "m04_wishlist", full=False)
    page.get_by_role("tab", name="Models").click()
    shot(page, "m05_models", full=False)
    page.locator(".model-card", has_text="Zero").click()
    page.wait_for_timeout(400)
    shot(page, "m06_model_panel", full=False)
    # Is anything wider than the screen (sideways scrolling)?
    width = page.evaluate("document.documentElement.scrollWidth")
    assert width <= 390, f"page is {width}px wide on a 390px phone"


with sync_playwright() as p:
    browser = p.chromium.launch()
    desk = browser.new_page(viewport={"width": 1280, "height": 860})
    watch(desk, "desktop")
    for fn in (inventory_loads, search, chip, condition_low, plus_minus, notes, edit_details, manage_lists,
               add_lookup, add_to_wishlist, wishlist_buy, delete_bought, scan_owned, scan_unknown,
               models, model_paste, add_model_hasegawa, undo, add_to_wishlist_button, duplicate_check, wishlist_panel, shop_tamiya, used_up,
               scalemates, fab_desktop, model_edit, lists_protect, no_panel):
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
