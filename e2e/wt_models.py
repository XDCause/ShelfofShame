"""The walk-through's steps: Models: kits, lookups, paints, the timer and build log, Gundam and Warhammer.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


def set_model(page, name, **fields):
    """Put a kit in the state a step needs first (the real data moves on; the run restores it after)."""
    [kit] = [m for m in page.request.get(f"{BASE}/api/models").json() if name in m["name"]]
    r = page.request.patch(f"{BASE}/api/models/{kit['model_id']}", data=fields)
    assert r.ok, r.text()


def open_model(page, name):
    go(page, "Models")
    page.locator(".model-card", has_text=name).click()
    return drawer(page)


@step("Models: shelf of shame, list and the Zero's checklist")
def models(page):
    go(page, "Models")
    expect(page.locator(".model-card")).to_have_count(MODELS)
    expect(page.locator(".stat-grid")).to_contain_text("Shelf of shame")
    kits = get_json("/api/models/summary")["all_kits"]   # every bought kit
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


@step("Model: Search Scalemates link")
def scalemates(page):
    go(page, "Models")
    page.locator(".model-card", has_text="Zero").click()
    link = drawer(page).get_by_role("link", name=re.compile("Search Scalemates"))
    expect(link).to_have_attribute("href", re.compile(r"scalemates\.com/search\.php\?q=Tamiya"))
    page.keyboard.press("Escape")


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
    chip = hobby.get_by_role("button", name=re.compile("^Warhammer"))
    chip.click()
    # Just the Warhammer kits: as many cards as the chip says (your own Warhammer kits are in the copied data too)
    expect(page.locator(".model-card")).to_have_count(int(re.search(r"(\d+)\s*$", chip.inner_text()).group(1)))
    expect(page.locator(".model-card", has_text="Intercessors")).to_contain_text("1 of 10 minis painted")
    shot(page, "d24_hobbies", full=False)
    hobby.get_by_role("button", name=re.compile("^All")).click()


@step("Build steps: an In progress kit shows the step underway")
def build_underway(page):
    set_model(page, "Zero", status="In progress")
    d = open_model(page, "Zero")
    expect(d.locator(".steps li.underway")).to_have_count(1)
    expect(d.locator(".section-head .pill")).to_contain_text("Now:")
    shot(page, "d30_build_underway", full=False)
    page.keyboard.press("Escape")


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
