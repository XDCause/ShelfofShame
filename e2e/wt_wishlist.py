"""The walk-through's steps: The wishlist: adding, buying, extras, shops, Shop Tamiya.
Run by walkthrough.py, in its order (split from it 2026-10-21)."""
from wt_common import *  # noqa: F401,F403 (the set-up, helpers and the step decorator)


def _wishlist_extras(page, tag):
    page.goto(BASE + "/wishlist")                       # a fresh load (the step before ends here, so a nav click wouldn't fetch the new kit)
    card = page.locator(".wanted-card", has_text=f"Kit {tag}")
    card.get_by_role("button", name="Details").click()
    d = drawer(page)
    d.get_by_label("Amount to put aside").fill("20")
    d.get_by_role("button", name="Put aside").click()
    expect(d).to_contain_text("Saved $20.00 of $54.00")
    d.get_by_label("A price you saw").fill("49.95")
    d.get_by_role("button", name="Add price").click()
    expect(d.locator(".wx-prices")).to_contain_text("$49.95")
    page.keyboard.press("Escape")
    expect(card).to_contain_text("Saved $20.00")
    card.locator(".wanted-tick").click()
    expect(card.locator(".wanted-tick")).to_have_attribute("aria-pressed", "true")
    page.locator(".inv-menu > summary").click()
    page.get_by_role("button", name="What I bought (history)").click()
    expect(page.locator(".wx-history")).to_contain_text(f"Kit {tag}")
    page.locator(".inv-menu > summary").click()
    page.get_by_role("button", name="Back to the wishlist").click()
    # add from a link (the walk-through's stand-in shop page)
    page.locator(".inv-menu > summary").click()
    page.get_by_role("button", name="Add from a shop link…").click()
    d = drawer(page)
    d.get_by_label("Product link").fill(f"https://shop.example.com/{tag}")
    d.get_by_role("button", name="Read it").click()
    expect(d.get_by_label("Name")).to_have_value("Stand-in Knee Pads")
    d.get_by_label("Name").fill(f"Pads {tag}")
    d.get_by_label("What is it").select_option("gear:volleyball")
    d.get_by_role("button", name="Add to my wishlist").click()
    expect(page.locator(".wanted-card", has_text=f"Pads {tag}")).to_be_visible()
    page.goto(BASE + "/wishlist/gift")
    expect(page.locator(".wx-gift-list").first).to_be_visible()


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


@step("Wishlist extras: details (save up, a price), tick a kit bought and it's in the history; add from a link; the gift list")
def wishlist_extras(page):
    tag = MARK.replace("e2e", "wk")
    kit = page.request.post(f"{BASE}/api/models", data={"name": f"Kit {tag}", "status": "Wanted", "price_paid": 54}).json()
    try:
        _wishlist_extras(page, tag)
    finally:                                          # (its kit and gear would change other steps' counts)
        page.request.delete(f"{BASE}/api/models/{kit['model_id']}")
        for g in page.request.get(f"{BASE}/api/gear").json():
            if g["name"] == f"Pads {tag}":
                page.request.delete(f"{BASE}/api/gear/{g['gear_id']}")


@step("Bought item is in inventory with today's date; delete it")
def delete_bought(page):
    go(page, "Supplies")
    page.locator("tr.row", has_text="XF2 Flat White").click()
    d = drawer(page)
    expect(d.get_by_label("Last bought from")).to_have_value("E2E shop")
    d.get_by_role("button", name="Remove", exact=True).click()
    page.get_by_role("button", name="Yes, remove").click()
    expect(page.locator("tr.row", has_text="XF2 Flat White")).to_have_count(0)


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
    expect(page.locator(".wish-head button")).to_have_count(1)              # just + Add
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


@step("Wishlist by shop: the default shop first, Good Games for board games; gear from Blue Sky (stand-in)")
def wishlist_shops(page):
    game = page.request.post(f"{BASE}/api/board-games", data={"name": f"Wantgame {MARK}", "status": "Wanted"}).json()
    go(page, "Wishlist")
    expect(page.locator(".shop-heading").first).to_contain_text(page.request.get(f"{BASE}/api/settings").json()["default_shop"])
    section = page.locator(".shop-section", has=page.locator(".shop-heading", has_text="Good Games"))
    expect(section.locator(".wanted-card", has_text=f"Wantgame {MARK}")).to_be_visible()
    page.locator(".inv-hobbies").get_by_role("button", name=re.compile("^Board games")).click()         # the hobby row
    expect(page.locator(".wanted-card", has_text=f"Wantgame {MARK}")).to_be_visible()
    page.locator(".inv-hobbies").get_by_role("button", name="All hobbies").click()
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
