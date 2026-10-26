"""The walk-through's steps: Home, Settings, navigation, banners, the calendar, goals and to-dos, signing in, the phone.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


# ---------------------------------------------------------------- desktop
@step("Home: greeting, every hobby's tiles, Coming up, and the numbers open their pages")
def home(page):
    page.goto(BASE)
    expect(page.locator(".hero h2")).to_have_text(re.compile("^Good (morning|afternoon|evening)(, .+)?$"), timeout=15000)   # (+ your name, if set)
    stats = page.locator(".home-stat")
    expect(stats.filter(has_text="Supplies")).to_contain_text(str(TOTAL))
    for tile in ("Shelf of shame", "Board games", "Volleyball", "Next game"):
        expect(stats.filter(has_text=tile)).to_be_visible()
    # supplies 2, models 2, board games 2, volleyball 2, video games 2 = 10; chess (+ puzzles), reading 1 each;
    # hiking, gardening, shooting and travel 2 each (2026-10-20: a second number each)
    expect(stats).to_have_count(10 + CHESS + CHESS_PUZZLES + READING + 2 * HIKING + 2 * GARDEN + 2 * SHOOTING + 2 * TRAVEL)
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
    expect(page.get_by_role("button", name="Scan a barcode")).to_have_count(0)    # scanning is for supplies: only there
    go(page, "Supplies")
    expect(page.get_by_role("button", name="Scan a barcode")).to_be_visible()


@step("Escape closes panels; no panel left open")
def no_panel(page):
    expect(page.locator("aside.drawer")).to_have_count(0)


@step("Top-bar search: Ctrl+K, type, Enter opens the kit")
def global_search(page):
    go(page, "Home")
    page.keyboard.press("Control+k")
    page.keyboard.type("Sherman")
    expect(page.locator(".search-results li").first).to_contain_text("Sherman")
    page.keyboard.press("Enter")
    expect(drawer(page).locator(".item-name")).to_contain_text("Sherman")
    page.keyboard.press("Escape")


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
    expect(page.locator(".banner-picture")).to_have_count(0)                    # the Picture button: off until Settings turns it on
    page.get_by_role("button", name="Settings").click()
    d.locator("summary", has_text="Appearance").click()
    d.get_by_label("Picture button on banners").check()
    page.keyboard.press("Escape")
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
    page.get_by_role("button", name="Settings").click()                          # tidy up: no name, no Picture button
    d.locator("summary", has_text="Appearance").click()
    d.get_by_label("Your name").fill("")
    d.get_by_label("Your name").press("Enter")
    d.get_by_label("Picture button on banners").uncheck()
    expect(page.locator(".banner-picture")).to_have_count(0)
    page.keyboard.press("Escape")


@step("Keyboard: a panel keeps Tab inside it, and closing it puts focus back on what opened it")
def panel_focus(page):
    go(page, "Home")
    settings = page.get_by_role("button", name="Settings")
    settings.focus()
    page.keyboard.press("Enter")
    expect(drawer(page)).to_be_visible()
    for _ in range(40):                                                          # round and round: never out of the panel
        page.keyboard.press("Tab")
        assert page.evaluate("document.querySelector('aside.drawer').contains(document.activeElement)"), "Tab left the panel"
    for _ in range(5):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate("document.querySelector('aside.drawer').contains(document.activeElement)"), "Shift+Tab left the panel"
    page.keyboard.press("Escape")
    expect(drawer(page)).to_have_count(0)
    expect(settings).to_be_focused()


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
    # every week on the grid: counted on NEXT month's, all after today (this month's can hold only 2 when it
    # starts late in the month - it failed on Monday 26 Oct 2026); then back to today for the steps below
    page.get_by_role("button", name="Next month").click()
    expect(page.locator(".day-event", has_text=MARK).nth(3)).to_be_visible()   # 4 at least
    page.get_by_role("button", name="Today").click()
    expect(detail).to_contain_text(f"Volleyball comp {MARK}")
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
    expect(detail.locator(".cal-planned", has_text=f"Volleyball comp {MARK}")).to_contain_text("Logged")
    expect(detail).to_contain_text("Volleyball vs Spikers")                    # what happened
    detail.get_by_role("button", name="Write about this day").click()
    expect(page).to_have_url(re.compile(r"/journal/\d+$"))
    page.go_back()


@step("Calendar extras: quick add in plain words, chosen weekdays, a countdown and a checklist, search, Week / Agenda / Year, Show, drag a day")
def calendar_extras(page):
    go(page, "Calendar")
    quick = page.get_by_label("Add an event in plain words")
    quick.fill(f"Club night {MARK} every mon and thu 7-9pm at the hall")
    expect(page.locator(".cal-quick-read")).to_contain_text("every Mon & Thu")
    expect(page.locator(".cal-quick-read")).to_contain_text("7pm–9pm")
    page.locator(".cal-quick-read").get_by_role("button", name="Add", exact=True).click()
    expect(page.locator(".toast")).to_contain_text(f"Club night {MARK} added")
    # a countdown with what to bring, made from quick add's "Edit first"
    quick.fill(f"Comp {MARK} in 10 days 8am")
    page.locator(".cal-quick-read").get_by_role("button", name="Edit first").click()
    d = drawer(page)
    d.get_by_role("switch", name=re.compile("Count down to it")).check()
    d.get_by_label("Add an item to bring").fill("Knee pads")
    page.keyboard.press("Enter")
    expect(d.locator(".cal-checklist")).to_contain_text("0/1 packed")
    d.get_by_role("button", name="Add event", exact=True).click()
    expect(page.locator(".cal-countdown", has_text=f"Comp {MARK}")).to_contain_text("10 days")
    # search finds it; Week, Agenda and Year show
    page.get_by_label("Search events").fill(f"club night {MARK}")
    expect(page.locator(".cal-search-list")).to_contain_text(f"Club night {MARK}")
    page.get_by_label("Search events").fill("")
    page.locator(".section-tabs").get_by_role("link", name="Week", exact=True).click()
    expect(page.locator(".cal-week-col")).to_have_count(7)
    page.locator(".section-tabs").get_by_role("link", name="Agenda", exact=True).click()
    expect(page.locator(".cal-agenda")).to_contain_text(f"Club night {MARK}")
    shot(page, "d31b_calendar_agenda", full=False)
    page.locator(".section-tabs").get_by_role("link", name="Year", exact=True).click()
    expect(page.locator(".cal-year-month")).to_have_count(12)
    page.locator(".section-tabs").get_by_role("link", name="Month", exact=True).click()
    # Show: hiding planned events hides them
    page.locator(".cal-menu > summary").click()
    page.locator(".cal-menu-body").get_by_label("Planned events").uncheck()
    expect(page.locator(".day-event", has_text=f"Club night {MARK}")).to_have_count(0)
    page.locator(".cal-menu-body").get_by_label("Planned events").check()
    page.locator(".cal-menu > summary").click()
    # drag one day of the repeating event to another day: that day only
    pill = page.locator(".day-event", has_text=f"Club night {MARK}").first
    before = page.locator(".day-event", has_text=f"Club night {MARK}").count()
    for attempt in range(2):                        # (a simulated HTML drag can miss right after a menu closes: once more)
        pill.drag_to(page.locator("button.day").nth(41))
        try:
            expect(page.get_by_text("Moved that day only")).to_be_visible(timeout=6000)
            break
        except AssertionError:
            if attempt:
                raise
    expect(page.locator(".day-event", has_text=f"Club night {MARK}")).to_have_count(before)


@step("To-do: added on Home and on its tab, ticked off (undo), a repeating one brings its next, details in its panel")
def todos(page):
    go(page, "Home")
    card = page.locator(".todo-home")
    expect(card.get_by_role("heading", name=re.compile("To do"))).to_be_visible()
    card.get_by_label("New to-do").fill(f"Buy primer {MARK}")
    card.get_by_role("button", name="Add", exact=True).click()
    expect(card.locator(".task-row", has_text=MARK)).to_be_visible()
    card.get_by_label(f"Done: Buy primer {MARK}").click()                       # ticked off on Home...
    expect(card.locator(".task-row.task-done", has_text=MARK)).to_be_visible()
    page.locator(".toast").get_by_role("button", name="Undo").click()           # ...and undone
    expect(card.locator(".task-row:not(.task-done)", has_text=MARK)).to_be_visible()
    card.get_by_role("link", name=re.compile("All")).click()
    expect(page).to_have_url(BASE + "/goals/todo")
    expect(page.locator(".section-tabs a[aria-current=page]")).to_have_text("To-do")
    page.get_by_label("New to-do").fill(f"Water the basil {MARK}")
    page.get_by_label("Due (optional)").fill(page.evaluate("new Date().toLocaleDateString('en-CA')"))
    page.get_by_role("button", name="Add", exact=True).click()
    today = page.locator(".task-group-today")
    expect(today.locator(".task-row", has_text="Water the basil")).to_be_visible()
    today.locator(".task-open", has_text="Water the basil").click()             # its panel: make it repeat, daily
    d = drawer(page)
    d.get_by_label("Repeats").select_option("daily")
    d.get_by_label("High priority").check()
    d.get_by_label("Hobby").select_option("gardening")
    d.get_by_role("button", name="Save").click()
    expect(d).to_have_count(0)
    row = today.locator(".task-row", has_text="Water the basil")
    expect(row.locator(".task-high")).to_be_visible()
    expect(row).to_contain_text("every day")
    expect(row).to_contain_text("Gardening")
    shot(page, "d61_todo", full=True)
    row.get_by_role("checkbox").click()
    expect(page.locator(".toast")).to_contain_text("Next one due tomorrow")
    page.reload()
    expect(page.locator(".task-group-week .task-row", has_text="Water the basil")).to_contain_text("Tomorrow")   # the next one
    page.locator(".section-tabs").get_by_role("link", name="Big picture", exact=True).click()   # the other tab: the goals
    expect(page).to_have_url(BASE + "/goals")


@step("Goals: a new goal - why, details, its to-dos, a number, a progress note, on track; reached (celebrated); deleted")
def goals(page):
    go(page, "Goals")
    page.get_by_role("button", name="+ New goal").first.click()
    page.get_by_label("What's the goal?").fill(f"Finish three kits {MARK}")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.get_by_label("Goal", exact=True)).to_have_value(f"Finish three kits {MARK}")
    expect(page.get_by_label("When")).to_have_value(re.compile(r"^year:\d{4}$"))           # new goals: this year's (Set up open)
    expect(page.locator(".goal-hero .goal-due")).to_contain_text(re.compile("31 Dec|Due in|Due today"))   # aims for 31 December
    expect(page.get_by_label("What it counts").locator("option", has_text=re.compile("^Books finished$"))).to_have_count(1)   # can count itself
    page.get_by_label("Why it matters").fill("The stash keeps growing.")
    page.get_by_label("Details").click()                             # leaving a box saves it
    page.get_by_label("Details").fill("One a month. Zero first.")
    todo = page.locator(".goal-next-up").get_by_label("New to-do")
    todo.fill("Finish the Zero")
    todo.press("Enter")
    expect(page.locator(".goal-next-up .task-row")).to_have_count(1)
    todo.fill("Prime the Sherman")
    todo.press("Enter")
    expect(page.locator(".goal-next-up .task-row")).to_have_count(2)
    page.get_by_label("Done: Finish the Zero").check()
    expect(page.locator(".goal-hero .goal-big-number")).to_have_text("50%")             # its to-dos measure it
    expect(page.locator(".goal-next-up")).to_contain_text("1 of 2 done")
    page.get_by_label("Unit").fill("kits")
    page.get_by_label("Target").fill("3")
    page.get_by_label("Target").press("Tab")
    page.get_by_label("Progress note").fill("Zero done, decals went on well")
    page.get_by_label("Number now").fill("1")
    page.get_by_role("button", name="Add note").click()
    expect(page.locator(".goal-notes li")).to_contain_text("1 kits · Zero done")
    expect(page.locator(".goal-hero .goal-big-percent")).to_have_text("33%")            # the number wins over the to-dos
    expect(page.locator(".goal-hero .goal-pace")).to_have_text(re.compile("Ahead|On track|Behind"))   # against an even pace
    expect(page.locator(".goal-chart svg")).to_be_visible()
    shot(page, "d60_goal", full=True)
    page.get_by_role("button", name="Mark as reached").click()
    expect(page.locator(".goal-reached")).to_contain_text("You did it")
    expect(page.locator(".goal-hero .goal-due")).to_contain_text("Reached")
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
    page.get_by_label("More for this goal").click()
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Delete goal").click()
    expect(page).to_have_url(re.compile(r"/goals$"))
    expect(page.locator(".goal-tile", has_text=MARK)).to_have_count(0)
    # Its to-dos stay on the list: tidy them away
    for t in page.request.get(f"{BASE}/api/todos?show=open").json() + page.request.get(f"{BASE}/api/todos?show=done").json():
        if t["title"] in ("Finish the Zero", "Prime the Sherman") and t["goal_id"] is None:
            page.request.delete(f"{BASE}/api/todos/{t['todo_id']}")


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


@step("Sign in: a stranger sees only the sign-in; a wrong password says so; the right one opens the app; signing out")
def sign_in_ui(page):
    page.goto(BASE)
    expect(page.get_by_role("heading", name="Welcome back")).to_be_visible(timeout=15000)
    expect(page.locator(".sidebar")).to_have_count(0)                          # none of the app shows
    page.get_by_label("Password").fill("not the password at all")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("isn't right")
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.locator(".hero h2")).to_have_text(re.compile("^Good "), timeout=15000)
    cookie = next(c for c in page.context.cookies() if c["name"] == COOKIE)
    assert cookie["httpOnly"] and cookie["secure"] and cookie["sameSite"] == "Strict", cookie
    shot(page, "a00_signed_in", full=False)
    page.get_by_role("button", name="Settings").click()
    drawer(page).locator("summary", has_text="Security").click()
    expect(drawer(page).locator(".security-list .pill", has_text="This device")).to_be_visible()
    expect(drawer(page).get_by_role("button", name="Set up an authenticator app")).to_be_visible()
    shot(page, "a01_security", full=False)
    drawer(page).get_by_role("button", name="Sign out of this device").click()
    expect(page.get_by_role("heading", name="Welcome back")).to_be_visible(timeout=15000)
    page.goto(BASE + "/supplies")                                              # a deep link still needs signing in
    expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
