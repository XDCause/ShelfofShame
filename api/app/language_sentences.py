"""Language learning's reading: real example sentences from Tatoeba (tatoeba.org, CC BY 2.0 FR), at your level
(A11_language_sentences.sql; loaded once by load-tatoeba.ps1 - no outside site is asked here).

    GET  /language/sentences?language_id=&level=&word=&limit=   sentences to read, each with its words marked known or
                                                                 not, its English, and its Tatoeba id (for the credit link)
                                                                   level=right  "just right": all but one word known (i+1)
                                                                   level=easy   every word known
                                                                   level=any    a random set
                                                                   word=        sentences with that word, the fewest
                                                                                unknown words first (level is ignored)
                                                                 Sentences you haven't read come first; the answer also
                                                                 says how many are loaded and how many are at each level.
    POST /language/sentences/{id}/seen        {language_id}           you've read it (the English was shown)
    POST /language/sentences/{id}/card        {language_id, word?}    the sentence into your deck as a CLOZE card on its
                                              unknown word (or the word you tapped): "Ayer {{fui}} al cine" - the word in
                                              context, with the English as its meaning and the Tatoeba link in its notes.
                                              A cloze rather than a whole-sentence card because its answer is a word
                                              (so it counts as known here at once and the next sentences move on), it
                                              tests recall rather than recognition, and the deck already reviews clozes.

"At your level", kept simple: the words you know are your deck's cards in this language - a word card's front (every
word of it: "el perro" gives el and perro; notes in brackets left out) and a cloze card's answers. Lessons you've
finished count too, since a lesson adds its words to the deck as cards. A sentence's words are compared folded
(langwords.fold: lower case, accents off, ñ kept), so "esta" is known when you have "está"; there's no stemming, so
"como" isn't known from "comer". Names and numbers aren't words to know (the loader leaves them out). A card counts
whatever its state - new, learning, suspended - since you've met the word.
"""
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from . import langwords
from .db import db, found, insert_row
from .language_cards import CARD_SELECT, CLOZE, _duplicate

router = APIRouter(prefix="/api", tags=["language"])

CREDIT = "Sentences from Tatoeba (tatoeba.org), CC BY 2.0 FR"
LICENCE_URL = "https://creativecommons.org/licenses/by/2.0/fr/"
SENTENCE_URL = "https://tatoeba.org/en/sentences/show/{}"
Level = Literal["right", "easy", "any"]
ID = {"ge": 1, "le": 2147483647}


# ---------------------------------------------------------------------------------------------
# What you know (pure: tested directly)
# ---------------------------------------------------------------------------------------------
def card_forms(kind: str, front: str) -> list[str]:
    """The folded words a card teaches: a cloze's answers ({{fui::ir}} -> fui), a word card's whole front (bar notes)."""
    if kind == "cloze":
        return [f for m in CLOZE.finditer(front or "") for f in langwords.forms(m.group(1).split("::")[0])]
    return langwords.forms(re.sub(r"\([^)]*\)", " ", front or ""))


def unknown_words(words: list[str], known: set[str]) -> list[str]:
    return [w for w in words if w not in known]


def marked(row: dict, known: set[str]) -> dict:
    """A sentence for the page: its pieces (each word marked known / unknown; names, numbers and punctuation are
    plain), its English, the unknown words, its link."""
    counted = set(row["words"])
    pieces = []
    for text, is_word in langwords.tokens(row["text"]):
        form = langwords.fold(text) if is_word else None
        if form is not None and form not in counted:
            form = None                                   # (a name)
        pieces.append({"text": text, "word": form, "unknown": form is not None and form not in known})
    return {"sentence_id": row["sentence_id"], "text": row["text"], "english": row["english"], "pieces": pieces,
            "unknown": unknown_words(row["words"], known), "word_count": row["word_count"], "rarity": row["rarity"],
            "seen": bool(row.get("seen")), "url": SENTENCE_URL.format(row["sentence_id"])}


def known_words(conn, language_id: int) -> set[str]:
    known = set()
    for c in conn.execute("SELECT kind, front FROM lang_cards WHERE language_id = %s", (language_id,)).fetchall():
        known.update(card_forms(c["kind"], c["front"]))
    return known


def _language(conn, language_id: int):
    return found(conn.execute("SELECT language_id, name, voice, course FROM lang_languages WHERE language_id = %s",
                              (language_id,)).fetchone(), "Language")


# ---------------------------------------------------------------------------------------------
# Sentences to read
# ---------------------------------------------------------------------------------------------
SENTENCE_COLS = "s.sentence_id, s.text, s.english, s.words, s.word_count, s.rarity, (v.sentence_id IS NOT NULL) AS seen"
HITS = """WITH k AS (SELECT DISTINCT unnest(%(known)s::text[]) AS word),
hits AS (SELECT sw.sentence_id, count(*)::int AS n FROM lang_sentence_words sw JOIN k USING (word)
         WHERE sw.course = %(course)s GROUP BY sw.sentence_id)"""


@router.get("/language/sentences")
def sentences(language_id: int = Query(**ID), level: Level = "right", word: str | None = Query(None, max_length=60),
              limit: int = Query(10, ge=1, le=50)):
    with db() as conn:
        lang = _language(conn, language_id)
        course = lang["course"]
        out = {"language": lang, "course": course, "credit": CREDIT, "licence_url": LICENCE_URL, "level": level,
               "word": None, "total": 0, "known_words": 0, "counts": {"right": 0, "easy": 0}, "sentences": []}
        if not course:
            return out
        out["total"] = conn.execute("SELECT count(*)::int AS n FROM lang_sentences WHERE course = %s", (course,)).fetchone()["n"]
        if not out["total"]:
            return out
        known = known_words(conn, language_id)
        out["known_words"] = len(known)
        args = {"known": sorted(known), "course": course, "lid": language_id, "limit": limit}
        if known:
            out["counts"] = conn.execute(HITS + """
                SELECT count(*) FILTER (WHERE s.word_count - h.n = 1)::int AS right,
                       count(*) FILTER (WHERE s.word_count = h.n)::int AS easy
                FROM hits h JOIN lang_sentences s USING (sentence_id)""", args).fetchone()
        seen_join = "LEFT JOIN lang_sentence_seen v ON v.language_id = %(lid)s AND v.sentence_id = s.sentence_id"
        folded = langwords.forms(word or "")
        if word is not None and word.strip():
            if len(folded) != 1:
                raise HTTPException(422, "Look up one word.")
            out["word"] = folded[0]
            rows = conn.execute(f"""SELECT {SENTENCE_COLS} FROM lang_sentence_words sw
                JOIN lang_sentences s USING (sentence_id) {seen_join}
                WHERE sw.course = %(course)s AND sw.word = %(word)s ORDER BY random() LIMIT 300""",
                                {**args, "word": folded[0]}).fetchall()
            rows.sort(key=lambda r: (len(unknown_words(r["words"], known)), r["seen"], r["rarity"]))
            rows = rows[:limit]
        elif level == "any":
            rows = conn.execute(f"""SELECT {SENTENCE_COLS} FROM lang_sentences s {seen_join}
                WHERE s.course = %(course)s ORDER BY (v.sentence_id IS NOT NULL), random() LIMIT %(limit)s""", args).fetchall()
        elif not known:
            rows = []
        else:
            gap = 1 if level == "right" else 0
            rows = conn.execute(HITS + f""" SELECT {SENTENCE_COLS} FROM hits h JOIN lang_sentences s USING (sentence_id)
                {seen_join} WHERE s.word_count - h.n = %(gap)s
                ORDER BY (v.sentence_id IS NOT NULL), random() LIMIT %(limit)s""", {**args, "gap": gap}).fetchall()
        out["sentences"] = [marked(r, known) for r in rows]
        return out


class SeenIn(BaseModel):
    language_id: int = Field(**ID)


class SentenceCardIn(SeenIn):
    word: str | None = Field(None, max_length=60)


def _sentence(conn, sentence_id: int, lang: dict):
    return found(conn.execute("SELECT sentence_id, course, text, english, words, word_count, rarity FROM lang_sentences "
                              "WHERE sentence_id = %s AND course IS NOT DISTINCT FROM %s",
                              (sentence_id, lang["course"])).fetchone(), "Sentence")


@router.post("/language/sentences/{sentence_id}/seen")
def mark_seen(body: SeenIn, sentence_id: int = Path(**ID)):
    with db() as conn:
        lang = _language(conn, body.language_id)
        _sentence(conn, sentence_id, lang)
        conn.execute("""INSERT INTO lang_sentence_seen (language_id, sentence_id) VALUES (%s, %s)
                        ON CONFLICT (language_id, sentence_id) DO UPDATE SET seen_at = now()""", (body.language_id, sentence_id))
    return {"seen": True}


def cloze_front(text: str, form: str) -> str | None:
    """The sentence with the first word that folds to `form` hidden: "Ayer {{fui}} al cine". None if it isn't there."""
    pieces = langwords.tokens(text.replace("{", "(").replace("}", ")"))
    for i, (piece, is_word) in enumerate(pieces):
        if is_word and langwords.fold(piece) == form:
            return "".join(p for p, _ in pieces[:i]) + "{{" + piece + "}}" + "".join(p for p, _ in pieces[i + 1:])
    return None


@router.post("/language/sentences/{sentence_id}/card", status_code=201)
def add_to_deck(body: SentenceCardIn, sentence_id: int = Path(**ID)):
    with db() as conn:
        lang = _language(conn, body.language_id)
        s = _sentence(conn, sentence_id, lang)
        if body.word and body.word.strip():
            forms = langwords.forms(body.word)
            if len(forms) != 1 or forms[0] not in s["words"]:
                raise HTTPException(422, "That word isn't in the sentence.")
            form = forms[0]
        else:
            unknown = unknown_words(s["words"], known_words(conn, body.language_id))
            if not unknown:
                raise HTTPException(422, "You know every word of it already: tap the word to learn.")
            form = unknown[0]
        front = cloze_front(s["text"], form)
        if front is None or len(front) > 500:
            raise HTTPException(422, "That sentence can't be made into a card.")
        _duplicate(conn, body.language_id, "cloze", front)
        card_id = insert_row(conn, "lang_cards", {
            "language_id": body.language_id, "kind": "cloze", "front": front, "back": s["english"][0][:500],
            "notes": f"From Tatoeba: {SENTENCE_URL.format(sentence_id)} (CC BY 2.0 FR)", "tags": ["tatoeba"]}, "card_id")
        conn.execute("""INSERT INTO lang_sentence_seen (language_id, sentence_id, card_id) VALUES (%s, %s, %s)
                        ON CONFLICT (language_id, sentence_id) DO UPDATE SET card_id = EXCLUDED.card_id""",
                     (body.language_id, sentence_id, card_id))
        return {"word": form, "card": conn.execute(CARD_SELECT + " WHERE c.card_id = %s", (card_id,)).fetchone()}
