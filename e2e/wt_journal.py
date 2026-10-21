"""The walk-through's steps: The journal: writing, links, suggestions, to-dos, drawing, writing mode, moods, extras.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


def scribble(page, surface, dx=0):
    """Draw a wavy line across the canvas with the mouse (the pen tool is picked up already)."""
    box = surface.bounding_box()
    x, y = box["x"] + box["width"] * 0.3 + dx, box["y"] + box["height"] * 0.45
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 25):
        page.mouse.move(x + i * 12, y + (20 if i % 2 else -20), steps=2)
    page.mouse.up()


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


@step("Journal extras: a template in a new notebook on lined paper, private, the prompt; Calendar, Map, Insights, a review, print")
def journal_extras(page):
    go(page, "Journal")
    page.locator(".jx-menu > summary").click()
    page.get_by_role("menuitem", name=re.compile("^Daily reflection")).click()
    expect(page).to_have_url(re.compile(r"/journal/\d+$"))
    expect(page.locator(".bn-editor")).to_contain_text("What went well", timeout=20000)
    page.get_by_label("Title").fill(f"Reflection {MARK}")
    page.get_by_label("Paper").select_option("lined")
    expect(page.locator(".journal-page[data-paper='lined']")).to_have_count(1)
    page.get_by_label("Notebook").select_option("new")
    page.get_by_label("New notebook's name").fill(f"Book {MARK}")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_label("Notebook")).to_contain_text(f"Book {MARK}")
    page.get_by_label("Private").click()
    expect(page.get_by_label("Private")).to_be_checked()
    expect(page.locator(".save-status")).to_have_text("Saved", timeout=10000)
    # private: not in the list until asked for, then in its notebook
    go(page, "Journal")
    expect(page.locator(".journal-card", has_text=f"Reflection {MARK}")).to_have_count(0)
    page.get_by_role("button", name="🔒 Private").click()
    expect(page.locator(".journal-card", has_text=f"Reflection {MARK}")).to_have_count(1)
    expect(page.locator(".journal-card", has_text=f"Reflection {MARK}")).to_contain_text(f"Book {MARK}")
    # an empty page offers a prompt; "Write about this" starts the page with it
    page.get_by_role("button", name="+ New page").click()
    prompt = page.locator(".jx-prompt-text").inner_text()
    page.get_by_role("button", name="Write about this").click()
    expect(page.locator(".bn-editor")).to_contain_text(prompt, timeout=20000)
    expect(page.locator(".jx-prompt")).to_have_count(0)
    page.get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Delete", exact=True).last.click()
    # the tabs
    page.locator(".section-tabs").get_by_role("link", name="Calendar").click()
    expect(page.locator(".jcal-streak")).to_contain_text("in a row")
    expect(page.locator(".jcal-day.today")).to_have_count(1)
    page.locator(".section-tabs").get_by_role("link", name="Map").click()
    expect(page.locator("section.page")).to_be_visible()
    page.locator(".section-tabs").get_by_role("link", name="Insights").click()
    expect(page.locator(".jin-stats")).to_contain_text("pages written")
    shot(page, "d38b_journal_insights", full=False)
    page.get_by_role("button", name="Write my weekly review").click()
    expect(page).to_have_url(re.compile(r"/journal/\d+$"))
    expect(page.locator(".bn-editor")).to_contain_text("Next week I want to", timeout=20000)
    expect(page.locator(".tag-chip")).to_have_text(re.compile("#review"))
    expect(page.locator(".suggestions")).to_have_count(0)                 # a review looks back: nothing to apply
    page.get_by_role("button", name="Delete").click()
    page.get_by_role("button", name="Delete", exact=True).last.click()
    page.get_by_role("link", name="Print / PDF").click()
    expect(page.locator(".jx-print-cover")).to_contain_text("pages")
    page.get_by_label("Include private pages").click()                    # (ticked by the address, a moment later)
    expect(page.get_by_label("Include private pages")).to_be_checked()
    expect(page.locator(".jx-printed", has_text=f"Reflection {MARK}")).to_have_count(1)


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
