"""Language learning's flashcards (A09_language.sql lang_cards / lang_reviews), scheduled by FSRS (srs.py).

    GET  /language/cards?language_id=&q=&tag=&state=   the deck (search the word, meaning, example; a tag; new / learning /
                                                        review / known / suspended / due)
    POST /language/cards                                one card: a word (front = the word, back = what it means) or a
                                                        cloze sentence ("Ayer {{fui}} al cine" - {{...}} is hidden;
                                                        {{fui::ir}} gives a hint)
    POST /language/cards/bulk                           paste many: one "word - meaning" a line (tab, =, -, en / em dash,
                                                        ; or : between them); a line with {{...}} is a cloze; # = a comment.
                                                        The same word twice (in the paste or the deck) is skipped
    GET / PATCH / DELETE /language/cards/{id}           (PATCH {suspended: true} takes it out of reviews; {reset: true}
                                                        makes it new again)
    GET  /language/review?language_id=                  today's queue: learning cards first, then cards due today, then new
                                                        cards up to the language's new-a-day limit; each with what every
                                                        grade would do (next: {1: '1m', 3: '4d'...})
    POST /language/cards/{id}/review                    an answer: grade 1 Again / 2 Hard / 3 Good / 4 Easy, how it was asked
                                                        (flip, type, listen, cloze), seconds taken; answers the card's new
                                                        memory and when it's due
    POST /language/reviews/{id}/undo                    take the last answer back (the card's memory before it is kept)
"""
import re
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from . import srs
from .db import db, found, insert_row, tidy_text, update_row
from .language import MATURE_DAYS, language_exists

router = APIRouter(prefix="/api", tags=["language"])

CLOZE = re.compile(r"\{\{(.+?)\}\}")
SEPARATORS = ("\t", " = ", " - ", " – ", " — ", " ; ", ";", " : ", ":")
TAG = re.compile(r"^[^\s,]{1,30}$")
Mode = Literal["flip", "type", "listen", "cloze"]
CardState = Literal["new", "learning", "review", "known", "suspended", "due"]


def parse_lines(text: str) -> tuple[list[dict], list[str]]:
    """Pasted lines -> cards ({kind, front, back}) and the lines that couldn't be read. Pure (tested directly)."""
    cards, bad = [], []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sep = next((s for s in SEPARATORS if s in line), None)
        if sep is None:
            bad.append(line)
            continue
        front, back = (part.strip() for part in line.split(sep, 1))
        if not front or not back or len(front) > 500 or len(back) > 500:
            bad.append(line)
            continue
        cards.append({"kind": "cloze" if CLOZE.search(front) else "word", "front": front, "back": back})
    return cards, bad


def _tags(tags):
    if tags is None:
        return None
    out = []
    for t in tags:
        t = t.strip().lower()
        if t and t not in out:
            if not TAG.match(t):
                raise ValueError("a tag is one word of up to 30 letters")
            out.append(t)
    return out[:20]


class CardFields(BaseModel):
    kind: Literal["word", "cloze"] | None = None
    front: str | None = Field(None, min_length=1, max_length=500)
    back: str | None = Field(None, min_length=1, max_length=500)
    example: str | None = Field(None, max_length=1000)
    example_meaning: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=5000)
    tags: list[str] | None = Field(None, max_length=50)

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, v):
        return _tags(v)


class CardIn(CardFields):
    language_id: int = Field(ge=1, le=2147483647)
    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=500)


class CardPatch(CardFields):
    suspended: bool | None = None
    reset: bool | None = None


class BulkIn(BaseModel):
    language_id: int = Field(ge=1, le=2147483647)
    text: str = Field(min_length=1, max_length=200000)
    tags: list[str] | None = Field(None, max_length=50)

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, v):
        return _tags(v)


class ReviewIn(BaseModel):
    grade: int = Field(ge=1, le=4)
    mode: Mode = "flip"
    seconds: int | None = Field(None, ge=0, le=3600)


CARD_SELECT = f"""SELECT c.card_id, c.language_id, c.kind, c.front, c.back, c.example, c.example_meaning, c.notes, c.tags,
       c.state, c.due, c.stability, c.difficulty, c.reps, c.lapses, c.last_review, c.learned_on, c.suspended, c.created_at,
       (c.state = 'review' AND c.stability >= {MATURE_DAYS}) AS known
FROM lang_cards c"""


def _check_cloze(kind, front):
    if kind == "cloze" and not CLOZE.search(front or ""):
        raise HTTPException(422, "A cloze card hides its answer in {{double braces}}: Ayer {{fui}} al cine.")


def _duplicate(conn, language_id, kind, front, not_id=None):
    if conn.execute("SELECT 1 FROM lang_cards WHERE language_id = %s AND kind = %s AND lower(front) = lower(%s) AND card_id <> %s",
                    (language_id, kind, front, not_id or 0)).fetchone():
        raise HTTPException(409, f"\"{front}\" is already in the deck.")


@router.get("/language/cards")
def list_cards(language_id: int | None = Query(None, ge=1, le=2147483647), q: str | None = Query(None, max_length=100),
               tag: str | None = Query(None, max_length=30), state: CardState | None = None,
               limit: int = Query(500, ge=1, le=5000)):
    where, args = [], []
    if language_id is not None:
        where.append("c.language_id = %s")
        args.append(language_id)
    if q and q.strip():
        where.append("(c.front ILIKE %s OR c.back ILIKE %s OR c.example ILIKE %s)")
        args += [f"%{q.strip()}%"] * 3
    if tag:
        where.append("%s = ANY(c.tags)")
        args.append(tag.lower())
    if state == "suspended":
        where.append("c.suspended")
    elif state == "known":
        where.append(f"c.state = 'review' AND c.stability >= {MATURE_DAYS}")
    elif state == "due":
        where.append("NOT c.suspended AND c.state <> 'new' AND c.due < (current_date + 1)::timestamptz")
    elif state:
        where.append("c.state = %s AND NOT c.suspended")
        args.append(state)
    sql = CARD_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY c.created_at DESC, c.card_id DESC LIMIT %s"
    with db() as conn:
        return conn.execute(sql, (*args, limit)).fetchall()


@router.post("/language/cards", status_code=201)
def add_card(body: CardIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("front", "back"))
    data.setdefault("kind", "cloze" if CLOZE.search(data["front"]) else "word")
    _check_cloze(data["kind"], data["front"])
    with db() as conn:
        language_exists(conn, body.language_id)
        _duplicate(conn, body.language_id, data["kind"], data["front"])
        card_id = insert_row(conn, "lang_cards", data, "card_id")
        return conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (card_id,)).fetchone()


@router.post("/language/cards/bulk", status_code=201)
def add_cards(body: BulkIn):
    cards, bad = parse_lines(body.text)
    if len(cards) > 2000:
        raise HTTPException(422, "That's more than 2,000 cards: paste them in parts.")
    added, skipped = 0, []
    with db() as conn:
        language_exists(conn, body.language_id)
        have = {(r["kind"], r["front"].lower()) for r in conn.execute(
            "SELECT kind, front FROM lang_cards WHERE language_id = %s", (body.language_id,)).fetchall()}
        for card in cards:
            key = (card["kind"], card["front"].lower())
            if key in have:
                skipped.append(card["front"])
                continue
            have.add(key)
            insert_row(conn, "lang_cards", {**card, "language_id": body.language_id, "tags": body.tags or []}, "card_id")
            added += 1
    return {"added": added, "skipped": skipped, "unreadable": bad}


@router.get("/language/cards/{card_id}")
def get_card(card_id: int):
    with db() as conn:
        card = found(conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (card_id,)).fetchone(), "Card")
        card["history"] = conn.execute("""SELECT reviewed_at, grade, mode, state_before, interval_days, seconds
                                          FROM lang_reviews WHERE card_id = %s ORDER BY reviewed_at DESC LIMIT 50""",
                                       (card_id,)).fetchall()
        return card


@router.patch("/language/cards/{card_id}")
def update_card(card_id: int, body: CardPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("front", "back"))
    reset = data.pop("reset", None)
    for required in ("kind", "front", "back", "suspended", "tags"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")
    with db() as conn:
        card = found(conn.execute("SELECT language_id, kind, front FROM lang_cards WHERE card_id = %s", (card_id,)).fetchone(), "Card")
        kind, front = data.get("kind", card["kind"]), data.get("front", card["front"])
        _check_cloze(kind, front)
        if "front" in data or "kind" in data:
            _duplicate(conn, card["language_id"], kind, front, card_id)
        if reset:
            data.update(state="new", due=datetime.now(timezone.utc), stability=None, difficulty=None, reps=0, lapses=0,
                        last_review=None, learned_on=None)
        update_row(conn, "lang_cards", "card_id", card_id, data)
        return conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (card_id,)).fetchone()


@router.delete("/language/cards/{card_id}", status_code=204)
def delete_card(card_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM lang_cards WHERE card_id = %s RETURNING card_id", (card_id,)).fetchone(), "Card")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Reviewing
# ---------------------------------------------------------------------------------------------
MEMORY = ("state", "due", "stability", "difficulty", "reps", "lapses", "last_review", "learned_on")
LEARN_AHEAD = "20 minutes"      # a learning card due within this is shown now (Anki's learn-ahead limit)


def _with_preview(card: dict, now: datetime) -> dict:
    card["next"] = srs.preview(card, now)
    return card


@router.get("/language/review")
def review_queue(language_id: int = Query(ge=1, le=2147483647), limit: int = Query(300, ge=1, le=1000)):
    now = datetime.now(timezone.utc)
    with db() as conn:
        lang = found(conn.execute("SELECT language_id, name, voice, new_per_day FROM lang_languages WHERE language_id = %s",
                                  (language_id,)).fetchone(), "Language")
        learning = conn.execute(CARD_SELECT + f""" WHERE c.language_id = %s AND NOT c.suspended
            AND c.state IN ('learning', 'relearning') AND c.due <= now() + interval '{LEARN_AHEAD}' ORDER BY c.due""",
                                (language_id,)).fetchall()
        due = conn.execute(CARD_SELECT + """ WHERE c.language_id = %s AND NOT c.suspended AND c.state = 'review'
            AND c.due < (current_date + 1)::timestamptz ORDER BY c.due LIMIT %s""", (language_id, limit)).fetchall()
        new_seen = conn.execute("""SELECT count(DISTINCT r.card_id)::int AS n FROM lang_reviews r JOIN lang_cards c USING (card_id)
                                   WHERE c.language_id = %s AND r.state_before = 'new' AND r.reviewed_at >= current_date::timestamptz""",
                                (language_id,)).fetchone()["n"]
        new_left = max(0, lang["new_per_day"] - new_seen)
        new = conn.execute(CARD_SELECT + """ WHERE c.language_id = %s AND NOT c.suspended AND c.state = 'new'
            ORDER BY c.created_at, c.card_id LIMIT %s""", (language_id, new_left)).fetchall() if new_left else []
        later = conn.execute("""SELECT min(due) AS at FROM lang_cards WHERE language_id = %s AND NOT suspended AND state <> 'new'
                                AND due >= (current_date + 1)::timestamptz""", (language_id,)).fetchone()["at"]
    # new cards mixed in among the reviews (one in every four), as Anki does, so a big pile of reviews doesn't hide them
    mixed, rest = [], list(due)
    for i, card in enumerate(new):
        mixed += rest[:3]
        rest = rest[3:]
        mixed.append(card)
    cards = learning + mixed + rest
    return {"language": lang, "cards": [_with_preview(c, now) for c in cards[:limit]], "new_left": new_left,
            "new_seen": new_seen, "next_due": later}


@router.post("/language/cards/{card_id}/review")
def answer(card_id: int, body: ReviewIn):
    now = datetime.now(timezone.utc)
    with db() as conn:
        card = found(conn.execute(CARD_SELECT + " WHERE c.card_id = %s FOR UPDATE OF c", (card_id,)).fetchone(), "Card")
        after = srs.review(card, body.grade, now)
        prev = {k: (card[k].isoformat() if hasattr(card[k], "isoformat") else card[k]) for k in MEMORY}
        update = {k: after[k] for k in ("state", "stability", "difficulty", "due", "reps", "lapses")}
        update["last_review"] = now
        if after["state"] == "review" and card["learned_on"] is None:
            update["learned_on"] = conn.execute("SELECT current_date AS d").fetchone()["d"]
        update_row(conn, "lang_cards", "card_id", card_id, update)
        review_id = insert_row(conn, "lang_reviews", {
            "card_id": card_id, "reviewed_at": now, "grade": body.grade, "mode": body.mode, "state_before": card["state"],
            "interval_days": after["interval_days"], "seconds": body.seconds, "prev": Jsonb(prev)}, "review_id")
        saved = conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (card_id,)).fetchone()
    return {"review_id": review_id, "card": _with_preview(saved, now), "again_today": after["interval_days"] == 0,
            "when": srs.label(after, now)}


@router.post("/language/reviews/{review_id}/undo")
def undo(review_id: int):
    """Take an answer back: the card's memory as it was before it. Only a card's latest answer can be taken back."""
    with db() as conn:
        r = found(conn.execute("SELECT card_id, prev FROM lang_reviews WHERE review_id = %s", (review_id,)).fetchone(), "Answer")
        latest = conn.execute("SELECT max(review_id) AS id FROM lang_reviews WHERE card_id = %s", (r["card_id"],)).fetchone()["id"]
        if latest != review_id or not r["prev"]:
            raise HTTPException(409, "Only the card's latest answer can be taken back.")
        prev = {k: r["prev"].get(k) for k in MEMORY}
        for k in ("due", "last_review"):
            prev[k] = datetime.fromisoformat(prev[k]) if prev[k] else None
        prev["due"] = prev["due"] or datetime.now(timezone.utc)
        prev["learned_on"] = date.fromisoformat(prev["learned_on"]) if prev["learned_on"] else None
        update_row(conn, "lang_cards", "card_id", r["card_id"], prev)
        conn.execute("DELETE FROM lang_reviews WHERE review_id = %s", (review_id,))
        return _with_preview(conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (r["card_id"],)).fetchone(),
                             datetime.now(timezone.utc))
