"""The walk-through's steps: The other hobbies: volleyball, board games, video games, chess, reading, hiking, gardening, shooting, travel.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


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
    with_dlc = [g for g in get_json("/api/videogames?show=started") if g.get("dlc_count")]
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
    # A hidden achievement you haven't got (when the data has one): kept secret until its eye is pressed; Show hidden
    # shows them all (the text is the stand-in's - SteamHunters isn't asked here)
    secret = None
    for g in get_json("/api/videogames?show=started")[:20]:
        a = next((a for a in get_json(f"/api/videogames/{g['app_id']}")["achievements"] if a["hidden"] and not a["achieved"]), None)
        if a:
            secret = (g, a)
            break
    if secret:
        g, a = secret
        page.get_by_label("Search your games").fill(g["name"])
        page.locator(".game-rows li", has_text=g["name"]).first.click()
        item = drawer(page).locator(".achievements li", has=page.locator(".item-title", has_text=a["name"])).first
        expect(item).to_contain_text("Hidden achievement")
        item.get_by_role("button", name=f"Show what {a['name']} says").click()
        expect(item).to_contain_text("(Stand-in) How to unlock")
        item.get_by_role("button", name=f"Hide what {a['name']} says").click()
        expect(item).to_contain_text("Hidden achievement")
        drawer(page).get_by_role("button", name=re.compile(r"^Show hidden \(\d+\)")).click()
        expect(item).to_contain_text("(Stand-in) How to unlock")
        shot(page, "d46_video_game_hidden", full=False)
        drawer(page).get_by_role("button", name="Hide hidden").click()
        expect(item).to_contain_text("Hidden achievement")
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
    # ...and your lifetime (no month arrows), then back to the month
    recap.get_by_role("button", name="Lifetime").click()
    expect(recap.locator(".home-card-title")).to_have_text("Lifetime")
    expect(recap.get_by_role("button", name="Month before")).to_have_count(0)
    recap.get_by_role("button", name="Month", exact=True).click()
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


@step("Travel: plan a trip (overseas), a to-do, a flight, money in yen (stand-in rates), a packing list ticked, a place found and on the map; trips, places and packing pages")
def travel(page):
    from datetime import datetime, timedelta, timezone
    # Brisbane's today, as the app's (UTC+10, no daylight saving): this container runs on UTC, a day behind before 10 am
    today = datetime.now(timezone(timedelta(hours=10))).date()
    start, end = today + timedelta(days=10), today + timedelta(days=14)
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
    for trip in get_json("/api/travel/trips"):
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
