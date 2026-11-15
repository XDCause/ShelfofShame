"""Chess opening theory, offline: Lichess's named openings (data/chess_openings.tsv - github.com/lichess-org/chess-openings,
public domain / CC0: ~3,900 named lines with their ECO code and moves). Read once, the first time it's needed.

    name_of(board)        the opening a position is (the deepest named position on the way to it counts)
    in_book(board)        is this position on a known line?
    theory(board)         the moves known lines play from here, each with the opening it leads to
    lines()               every named line: (eco, name, [san...]) - the opening trainer's tree
    search(text)          named lines whose name has every word (the trainer's "pick an opening")

A position is keyed by its EPD (pieces, side to move, castling, en passant - not the move counters), so a line reached
by another move order still counts.
"""
from functools import lru_cache
from pathlib import Path

import chess

DATA = Path(__file__).parent / "data" / "chess_openings.tsv"


def key(board: chess.Board) -> str:
    return board.epd()


@lru_cache(maxsize=1)
def _book() -> dict:
    """{"lines": [(eco, name, sans)], "named": {epd: (eco, name, plies)}, "next": {epd: {san: epd_after}}}"""
    lines, named, nxt = [], {}, {}
    for row in DATA.read_text(encoding="utf-8").splitlines()[1:]:
        eco, name, pgn = row.split("\t")
        board, sans = chess.Board(), []
        for token in pgn.split():
            if token.endswith(".") or token[0].isdigit() and "." in token:
                continue
            here = key(board)
            board.push_san(token)
            sans.append(token)
            nxt.setdefault(here, {})[token] = key(board)
        lines.append((eco, name, sans))
        k = key(board)
        if k not in named or len(sans) < named[k][2]:        # the shortest way there names it
            named[k] = (eco, name, len(sans))
    return {"lines": lines, "named": named, "next": nxt}


def lines() -> list[tuple[str, str, list[str]]]:
    return _book()["lines"]


def in_book(board: chess.Board) -> bool:
    b = _book()
    k = key(board)
    return k in b["named"] or k in b["next"]


def named(board: chess.Board) -> dict | None:
    """The opening this exact position is named as, if it is one."""
    hit = _book()["named"].get(key(board))
    return hit and {"eco": hit[0], "name": hit[1]}


def name_of(boards: list[chess.Board]) -> dict | None:
    """The opening of a game: the last named position among its positions (from the start)."""
    found = None
    for b in boards:
        found = named(b) or found
    return found


def theory(board: chess.Board) -> list[dict]:
    """The moves known lines continue with from here: [{san, name}] - the name of the line it leads to, if any (the
    deepest named position reachable by that move alone is too far; it's the move's own position or the nearest named
    one after it on a line)."""
    b = _book()
    out = []
    for san, after in b["next"].get(key(board), {}).items():
        hit = b["named"].get(after)
        if not hit:                                         # the move's position isn't named itself: the first line through it
            hit = next(((e, n, len(s)) for e, n, s in b["lines"] if _passes(s, board, san)), None)
        out.append({"san": san, "eco": hit and hit[0], "name": hit and hit[1]})
    return out


def _passes(sans: list[str], board: chess.Board, san: str) -> bool:
    """Does this line go through `board` and then play `san`?"""
    probe, target = chess.Board(), key(board)
    for i, s in enumerate(sans):
        if key(probe) == target:
            return i < len(sans) and sans[i] == san
        probe.push_san(s)
    return False


def search(text: str, limit: int = 30) -> list[dict]:
    """Named lines whose name has every word of `text` (the opening trainer's "pick an opening to learn"): names that
    start with it first, then shorter names (the main lines before their sub-variations)."""
    words = text.lower().split()
    if not words:
        return []
    hits = []
    for eco, name, sans in lines():
        low = name.lower()
        if all(w in low for w in words):
            hits.append((0 if low.startswith(words[0]) else 1, len(sans), name, eco, sans))
    hits.sort(key=lambda h: h[:3])
    return [{"eco": eco, "name": name, "moves": " ".join(sans), "plies": len(sans)} for _, _, name, eco, sans in hits[:limit]]
