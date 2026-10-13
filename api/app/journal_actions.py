"""Turning journal pages into actions.

Suggestions: a block that @mentions a model or a supply and says what happened offers the
change, for the user to apply with one tap (never automatically):
    "Just bought @Sherman and started it right away"   -> Sherman: In progress
    "Primed the @Zero today"                            -> Zero: build step Primed
    "I want to buy new @XF-10 for a new project"        -> XF-10: add to the wishlist
    "Played @Catan with Sam and Jo"                     -> Catan: log a play on the page's day
When a block says several things ("bought ... and started"), the word written last wins: it's
where the story ends. Only changes that move a model forward are offered, so a suggestion goes
away once it's applied (or the model has moved on), and one waved away stays away (dismissed).

To-dos: the editor's check-list blocks ({"type": "checkListItem", "props": {"checked": false}})
on every page are one to-do list, which can be ticked off without opening the page.
"""
import re

from .db import STAGES
from .journal_text import inline_text, mentions
from .wishlist import ON_WISHLIST

# Words -> the status they suggest, and the statuses it makes sense to move from.
STATUS_WORDS = [
    (r"bought|purchased|picked up|ordered|arrived|got (?:a|the|my|it)", "In stash", {"Wanted"}),
    (r"started|starting|began|begun|kicked off|working on|cracked open", "In progress", {"Wanted", "In stash", "On hold"}),
    (r"on hold|paused|shelved|put aside|set aside", "On hold", {"In progress"}),
    (r"finished|completed|done with|wrapped up", "Finished", {"Wanted", "In stash", "In progress", "On hold"}),
    (r"sold|gave away|given away|traded", "Gone", {"Wanted", "In stash", "In progress", "On hold", "Finished"}),
]

# Words -> a build step (only offered when that step is one of the model's hobby's steps).
STEP_WORDS = {
    "Built": r"built|assembled|assembly (?:is )?done",
    "Primed": r"primed|priming|primer(?:ed)? on",
    "Painted": r"painted|base ?coated",
    "Panel lined": r"panel[- ]?lin(?:ed|ing)",
    "Decals": r"decal(?:s|ed|ing)",
    "Weathered": r"weathered|weathering",
    "Top coat": r"top[- ]?coat(?:ed|ing)?|clear[- ]?coat(?:ed)?",
    "Based": r"based|basing",
}


# Words saying you want (more of) a supply. "bought" isn't one: that's already done.
BUY_WORDS = (r"want(?:s|ed)? to (?:buy|get|order)|need(?:s)? (?:to buy|to get|more|another|a new|some)|"
             r"buy(?:ing)?|order(?:ing)?|restock|re-?order|pick up|get (?:more|another|a new|some)|"
             r"running low on|ran out of|run out of|out of|low on|(?:add|put) (?:it )?(?:on|to) (?:the|my) wishlist")


# Words saying you played a board game (on the page's day).
PLAY_WORDS = r"play(?:ed|ing)?|games? night|won|lost|beat|taught|learn(?:ed|t)"


def _last(pattern: str, text: str) -> int:
    """Where the last match of `pattern` (whole words) ends in `text`, or -1."""
    ends = [m.end() for m in re.finditer(rf"\b(?:{pattern})\b", text, re.I)]
    return ends[-1] if ends else -1


def _latest(found):
    """Of (position, value) pairs, the value found furthest along the text (None if none were)."""
    hits = [(pos, value) for pos, value in found if pos >= 0]
    return max(hits, key=lambda h: h[0])[1] if hits else None


def _blocks(blocks):
    """Every block, nested ones included."""
    for block in blocks or []:
        if isinstance(block, dict):
            yield block
            yield from _blocks(block.get("children"))


def suggestions(conn, page: dict) -> list[dict]:
    """What the page's words suggest doing to the models it mentions (not yet done or dismissed)."""
    wanted = {}   # (model_id, field) -> what the words say
    supplies = set()
    games = set()
    for block in _blocks(page["content"]):
        mentioned = mentions(block.get("content"))
        text = inline_text(block.get("content"))
        if _last(BUY_WORDS, text) >= 0:
            supplies |= {target for kind, target in mentioned if kind == "supply"}
        if _last(PLAY_WORDS, text) >= 0:
            games |= {target for kind, target in mentioned if kind == "game"}
        ids = {target for kind, target in mentioned if kind == "model"}
        if not ids:
            continue
        status = _latest((_last(words, text), (to, start)) for words, to, start in STATUS_WORDS)
        step = _latest((_last(words, text), step) for step, words in STEP_WORDS.items())
        for model_id in ids:
            if status:
                wanted[(model_id, "status")] = status
            if step:
                wanted[(model_id, "stage")] = step
    result = _supply_suggestions(conn, page, supplies) + _play_suggestions(conn, page, games)
    if not wanted:
        return result

    models = {m["model_id"]: m for m in conn.execute(
        "SELECT model_id, name, hobby, status, stage, purchase_date, started_on FROM models WHERE model_id = ANY(%s)",
        (list({model_id for model_id, _ in wanted}),)).fetchall()}
    for (model_id, field), found in sorted(wanted.items()):
        m = models.get(model_id)
        if m is None:
            continue
        if field == "status":
            to, start = found
            if m["status"] not in start:
                continue
            changes = {"status": to}
            if to == "In stash" and m["purchase_date"] is None:
                changes["purchase_date"] = page["entry_date"]
            if to == "In progress" and m["started_on"] is None:
                changes["started_on"] = page["entry_date"]
            label = f"Mark as {to}"
        else:
            step = found
            steps = STAGES[m["hobby"]]
            if step not in steps or (m["stage"] in steps and steps.index(m["stage"]) >= steps.index(step)):
                continue
            changes = {"stage": step}
            label = f"Tick build step {step}"
        key = f"model:{model_id}:{field}:{changes[field]}"
        if key in page.get("dismissed", []):
            continue
        result.append({"key": key, "kind": "model", "id": model_id, "name": m["name"], "label": label,
                       "changes": changes})
    return result


def _supply_suggestions(conn, page: dict, supply_ids: set[int]) -> list[dict]:
    """"Add to wishlist" for supplies the page says you want, unless they're on it already."""
    if not supply_ids:
        return []
    rows = conn.execute(f"SELECT s.supply_id, s.name, {ON_WISHLIST} AS on_wishlist FROM supplies s "
                        "WHERE s.supply_id = ANY(%s) ORDER BY s.name", (list(supply_ids),)).fetchall()
    result = []
    for s in rows:
        key = f"supply:{s['supply_id']}:wishlist:yes"
        if s["on_wishlist"] or key in page.get("dismissed", []):
            continue
        result.append({"key": key, "kind": "supply", "id": s["supply_id"], "name": s["name"],
                       "label": "Add to wishlist", "changes": {"wishlist": True}})
    return result


def _play_suggestions(conn, page: dict, game_ids: set[int]) -> list[dict]:
    """"Log a play" for board games the page says you played, unless one is logged for that day."""
    if not game_ids:
        return []
    rows = conn.execute("SELECT g.game_id, g.name, EXISTS (SELECT 1 FROM board_game_plays p WHERE p.game_id = g.game_id "
                        "AND p.played_on = %s) AS logged FROM board_games g WHERE g.game_id = ANY(%s) ORDER BY g.name",
                        (page["entry_date"], list(game_ids))).fetchall()
    result = []
    for g in rows:
        key = f"game:{g['game_id']}:play:{page['entry_date']}"
        if g["logged"] or key in page.get("dismissed", []):
            continue
        result.append({"key": key, "kind": "game", "id": g["game_id"], "name": g["name"],
                       "label": "Log a play", "changes": {"played_on": str(page["entry_date"])}})
    return result


# ---------------------------------------------------------------------------
# To-dos
# ---------------------------------------------------------------------------
def todos_in(page: dict) -> list[dict]:
    """The check-list blocks on one page."""
    return [{"page_id": page["page_id"], "title": page["title"], "icon": page["icon"],
             "entry_date": page["entry_date"], "block_id": b.get("id"),
             "text": inline_text(b.get("content")).strip(), "checked": bool(b.get("props", {}).get("checked"))}
            for b in _blocks(page["content"]) if b.get("type") == "checkListItem" and b.get("id")]


def set_checked(content: list, block_id: str, checked: bool) -> bool:
    """Tick or untick one check-list block (in place). False if there's no such block."""
    for block in _blocks(content):
        if block.get("id") == block_id and block.get("type") == "checkListItem":
            block.setdefault("props", {})["checked"] = checked
            return True
    return False
