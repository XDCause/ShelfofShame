"""The browser walk-through: runs every step (wt_<area>.py) in ORDER on a desktop, then the phone, and reports.
Steps build on each other, so ORDER matters. A step that isn't in ORDER stops the run before it starts (a step
that was written but never added to the list used to be skipped quietly).
E2E_STEPS=name,name (run_e2e.ps1 -Steps / -Failed): only those steps, in ORDER - to check a fix quickly. A step that
needs an earlier one's data fails alone too: then name both (or run them all). Failed steps go in /out/failed.txt."""
import os
import wt_core, wt_hobbies, wt_journal, wt_models, wt_supplies, wt_wishlist
from wt_common import *  # noqa: F401,F403

# The desktop run, in order (the phone and the sign-in run on their own pages).
ORDER = [
    "home",
    "inventory_loads",
    "search",
    "chip",
    "groups",
    "supplies_hobbies",
    "supplies_tools",
    "condition_low",
    "plus_minus",
    "notes",
    "edit_details",
    "settings",
    "add_lookup",
    "add_to_wishlist",
    "wishlist_buy",
    "wishlist_extras",
    "delete_bought",
    "scan_owned",
    "scan_unknown",
    "models",
    "model_paste",
    "add_model_hasegawa",
    "add_model_trumpeter",
    "undo",
    "add_to_wishlist_button",
    "duplicate_check",
    "wishlist_panel",
    "shop_tamiya",
    "used_up",
    "scalemates",
    "desktop_tabs",
    "model_edit",
    "lists_protect",
    "kit_paints",
    "timer",
    "build_log",
    "stash",
    "mixes",
    "matches",
    "used_on",
    "gundam",
    "bandai_lookup",
    "warhammer",
    "journal_write",
    "journal_links",
    "journal_from_model",
    "journal_suggestion",
    "journal_todo",
    "global_search",
    "journal_wishlist",
    "banners",
    "panel_focus",
    "appearance",
    "build_underway",
    "calendar",
    "volleyball",
    "board_games",
    "whiteboard",
    "sketch_block",
    "writing_mode",
    "journal_extras",
    "calendar_extras",
    "mood",
    "video_games",
    "chess",
    "reading",
    "warhammer_range",
    "warhammer_minis",
    "gundam_range",
    "board_game_kinds",
    "board_game_elsewhere",
    "volleyball_coach",
    "video_game_friends",
    "wishlist_shops",
    "goals",
    "todos",
    "supply_kit",
    "hiking",
    "gardening",
    "shooting",
    "travel",
    "bunnings_button",
    "settings_more",
    "no_panel",
]
AREAS = (wt_core, wt_hobbies, wt_journal, wt_models, wt_supplies, wt_wishlist)   # (importing them registers their steps)
ON_THEIR_OWN = {"phone", "sign_in_ui"}
_left_out = sorted(set(STEPS) - set(ORDER) - ON_THEIR_OWN)
_unknown = [n for n in ORDER if n not in STEPS]
if _left_out or _unknown:
    print("Walk-through set-up problem:" + (f" steps not in ORDER: {', '.join(_left_out)}." if _left_out else "")
          + (f" ORDER names unknown steps: {', '.join(_unknown)}." if _unknown else ""))
    raise SystemExit(2)


ONLY = {s.strip() for s in os.environ.get("E2E_STEPS", "").split(",") if s.strip()}
if ONLY - set(STEPS):
    print(f"No such step: {', '.join(sorted(ONLY - set(STEPS)))}. The steps are the function names in ORDER.")
    raise SystemExit(2)


def sign_in_page(browser, zone):
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, timezone_id=zone, ignore_https_errors=True)
    page = ctx.new_page()
    watch(page, "sign-in")
    STEPS["sign_in_ui"](page)
    ctx.close()


with sync_playwright() as p:
    browser = p.chromium.launch()
    # The user's time zone: "today" in the browser must be the same day the app dates pages by.
    zone = "Australia/Brisbane"
    if not ONLY or "sign_in_ui" in ONLY:
        sign_in_page(browser, zone)
    desk = signed_in(browser.new_context(viewport={"width": 1280, "height": 860}, timezone_id=zone, ignore_https_errors=True)).new_page()
    watch(desk, "desktop")
    for name in ORDER:
        if not ONLY or name in ONLY:
            STEPS[name](desk)
    if not ONLY or "phone" in ONLY:
        ctx = signed_in(browser.new_context(**p.devices["iPhone 13"], timezone_id=zone, ignore_https_errors=True))
        mob = ctx.new_page()
        watch(mob, "phone")
        STEPS["phone"](mob)
    browser.close()

with open(f"{OUT}/failed.txt", "w") as f:     # for run_e2e.ps1 -Failed
    f.write(",".join(failed_steps))

for name, status, info in results:
    print(f"{status}  {name}  ({info})")
print(f"\n{sum(r[1] == 'PASS' for r in results)}/{len(results)} steps passed")
print("\nBrowser errors:" if errors else "\nBrowser errors: none")
for e in errors:
    print("  " + e)
raise SystemExit(0 if all(r[1] == "PASS" for r in results) and not errors else 1)
