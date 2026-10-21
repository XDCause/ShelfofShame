"""The walk-through's steps: Supplies: the list, filters, +/- and history, scanning, places and tools, kits.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


@step("Supplies loads with every item (the old address still works)")
def inventory_loads(page):
    page.goto(BASE + "/models/inventory")                   # where it used to be...
    expect(page).to_have_url(BASE + "/supplies")            # ...moves to the core page
    expect(page.locator(".navbar h1")).to_contain_text("Hobby supplies")
    expect(page.locator("tr.row").first).to_be_visible(timeout=15000)
    models = page.get_by_role("button", name=re.compile(r"^Models \d+$"))    # (other hobbies' kit shows too: just the supplies)
    if models.count():
        models.click()
    expect(page.locator("tr.row")).to_have_count(TOTAL)
    shot(page, "d01_inventory")


@step("Search narrows the list and the total follows")
def search(page):
    page.get_by_label("Search", exact=True).fill("flat")
    expect(page.locator("tr.row")).not_to_have_count(TOTAL, timeout=5000)
    expect(page.get_by_role("button", name="Clear filters")).to_be_visible()
    n = page.locator("tr.row").count()
    assert 0 < n < TOTAL, n
    shot(page, "d02_search_flat", full=False)
    page.get_by_label("Search", exact=True).fill("")
    expect(page.locator("tr.row")).to_have_count(TOTAL)


@step("Options: the category filter narrows the list, Every category clears it")
def chip(page):
    page.locator(".inv-menu > summary").click()
    page.get_by_label("Category").select_option("Paint")
    expect(page.locator("tr.row")).to_have_count(PAINTS)
    expect(page.locator(".inv-menu > summary")).to_contain_text("1 on")
    page.get_by_label("Category").select_option("")
    page.locator(".inv-menu > summary").click()
    expect(page.locator("tr.row")).to_have_count(TOTAL)


@step("Groups: close one, close all, remembered after a reload, search opens them")
def groups(page):
    expect(page.get_by_label("Group by")).to_have_value("category")
    paint = page.locator("details.inv-group", has=page.locator("summary", has_text=re.compile(r"^Paint")))
    expect(paint.locator("summary .fold-detail")).to_have_text(str(PAINTS))
    paint.locator("summary").click()
    expect(paint.locator("tr.row").first).to_be_hidden()
    expect(page.locator("tr.row:visible")).to_have_count(TOTAL - PAINTS)
    page.locator(".inv-menu > summary").click()                      # (Group / Sort / Close all live under Options)
    page.get_by_role("button", name="Close all groups").click()
    expect(page.locator("tr.row:visible")).to_have_count(0)
    shot(page, "d02b_groups_closed", full=False)
    page.reload()
    expect(page.locator("details.inv-group").first).to_be_visible(timeout=15000)
    expect(page.locator("tr.row:visible")).to_have_count(0)      # remembered
    page.get_by_label("Search", exact=True).fill("XF1 Flat Black")
    expect(page.locator("tr.row:visible", has_text="Acrylic XF1 Flat Black")).to_be_visible()
    page.get_by_label("Search", exact=True).fill("")
    expect(page.locator("tr.row:visible")).to_have_count(0)      # closed again after the search
    page.locator(".inv-menu > summary").click()
    page.get_by_role("button", name="Open all groups").click()
    expect(page.locator("tr.row:visible")).to_have_count(TOTAL)


@step("Supplies: every hobby's kit - pick a hobby, then one of its kinds; a row opens its panel")
def supplies_hobbies(page):
    tag = MARK.replace("e2e", "sup")                  # (not MARK itself: the Volleyball step looks for its own gear by it)
    made = [page.request.post(f"{BASE}/api/gear", data={"name": name, "hobby": "volleyball", "kind": kind}).json()
            for name, kind in ((f"Pads {tag}", "Knee pads"), (f"Ball {tag}", "Ball"))]
    page.reload()
    page.get_by_role("button", name=re.compile(r"^Volleyball \d+$")).click()
    expect(page.locator("tr.row", has_text=f"Pads {tag}")).to_be_visible()
    expect(page.locator("tr.row", has_text="XF1 Flat Black")).to_have_count(0)        # no model supplies here
    expect(page.locator("details.inv-group summary", has_text="Knee pads")).to_be_visible()   # its kinds are headings
    page.locator("tr.row", has_text=f"Pads {tag}").click()
    expect(drawer(page)).to_contain_text(f"Pads {tag}")
    page.keyboard.press("Escape")
    page.get_by_role("button", name=re.compile(r"^All hobbies")).click()
    expect(page.locator(".inv-hobby-title", has_text="Volleyball")).to_be_visible()
    shot(page, "d02c_supplies_hobbies", full=False)
    page.get_by_role("button", name=re.compile(r"^Models \d+$")).click()
    expect(page.locator("tr.row")).to_have_count(TOTAL)
    for g in made:
        page.request.delete(f"{BASE}/api/gear/{g['gear_id']}")


@step("Supplies tools: places that nest, a QR label, a place's page moves a paint in, shopping, stocktake, value report, select several")
def supplies_tools(page):
    tag = MARK.replace("e2e", "pl")
    rack = page.request.post(f"{BASE}/api/places", data={"name": f"Rack {tag}"}).json()
    drawer = page.request.post(f"{BASE}/api/places", data={"name": "Top drawer", "parent_id": rack["id"]}).json()
    page.goto(BASE + "/supplies/places")
    row = page.locator(".sx-places li", has_text="Top drawer").filter(has=page.locator(f"a[href='/supplies/place/{drawer['id']}']"))
    row.locator("input[type=checkbox]").check()
    page.get_by_role("link", name="Print 1 label").click()
    label = page.locator(".sx-label img")
    expect(label).to_be_visible()
    page.wait_for_function("() => document.querySelector('.sx-label img').naturalWidth > 0")     # the QR code drew
    page.goto(BASE + f"/supplies/place/{drawer['id']}")
    expect(page.locator(".sx-title")).to_contain_text(f"Rack {tag} › Top drawer")
    page.get_by_label("Find a supply to move here").fill("XF1 Flat")
    page.locator(".row-button", has_text="Move here").first.click()
    expect(page.locator(".card", has_text="In here")).to_contain_text("XF1 Flat Black")
    page.goto(BASE + "/supplies/shop")
    expect(page.locator(".sx-title")).to_contain_text("Shopping at")
    page.goto(BASE + "/supplies/stocktake")
    first = page.locator(".sx-count-card h3").inner_text()
    page.locator(".sx-count-actions .primary").click()
    expect(page.locator(".sx-count-card h3")).not_to_have_text(first)
    page.goto(BASE + "/supplies/report")
    expect(page.locator(".sx-report-part").first).to_be_visible()
    page.goto(BASE + "/supplies")
    page.locator(".inv-menu > summary").click()
    page.get_by_role("button", name="Select several…").click()
    page.locator("tr.row").nth(0).click()
    page.locator("tr.row").nth(1).click()
    expect(page.locator(".inv-bulk")).to_contain_text("2 selected")
    shot(page, "d02d_supplies_select", full=False)
    page.locator(".inv-bulk").get_by_role("button", name="Done").click()
    expect(page.locator(".inv-bulk")).to_have_count(0)


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
    expect(page.get_by_role("button", name=re.compile("need attention"))).to_be_visible()
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


@step("Duplicate check while typing a name")
def duplicate_check(page):
    page.get_by_role("button", name="+ Add", exact=True).click()
    d = drawer(page)
    d.get_by_label("Name / colour").fill("Flat Black")
    expect(d.locator(".similar")).to_contain_text("Acrylic XF1 Flat Black")
    shot(page, "d13_duplicate_check")
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


@step("Settings lists: brand used only by a model can't be removed")
def lists_protect(page):
    page.get_by_role("button", name="Settings").click()
    drawer(page).locator("details.lookup", has_text="Brands").locator("summary").click()
    expect(drawer(page).get_by_role("button", name="Remove Hasegawa")).to_be_disabled()
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
