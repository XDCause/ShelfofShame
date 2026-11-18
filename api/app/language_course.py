"""Language learning's built-in courses (A10_language_course.sql): the app teaches a language, lesson by lesson, as
Duolingo does - not just reviews the cards you made. The content is plain JSON written for the app,
data/courses/<code>/uNN.json (data/courses/README.md has the format); this module reads and checks it once (a unit with
a mistake is left out with a logged warning, the rest still work; tests/test_language_course.py fails on it), keeps
what you've done, and turns a finished lesson into cards. The exercises themselves are made in the browser from the
lesson's content (web/src/modules/language/lessonMaker.js).

    GET  /language/courses                                  the courses there are (code, name, units, lessons)
    GET  /language/languages/{id}/course                    a language's course: units -> lessons, each done (best and
                                                            last score, times) / unlocked (the one before is done) /
                                                            next; each unit's progress; the next lesson
    GET  /language/course/lessons/{lesson_id}               a lesson's content (notes, items, sentences - each with its
                                                            gap word), its unit, and earlier lessons' items (the wrong
                                                            options in multiple choice)
    POST /language/languages/{id}/lessons/{lesson_id}/done  {score, mistakes, seconds}: recorded; the lesson's items go
                                                            into the deck as word cards and its sentences as cloze cards
                                                            (the gap word hidden) - ones already there are skipped; the
                                                            seconds count as study minutes (language.MINUTES). Answers
                                                            what was added and the next lesson

A language follows a course through lang_languages.course: set by itself when a language named Spanish / Español is
added (course_for_name), and choosable in the language's panel.
"""
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .db import db, found

router = APIRouter(prefix="/api", tags=["language"])
log = logging.getLogger("uvicorn.error")

COURSES_DIR = Path(__file__).parent / "data" / "courses"
# The courses the app knows how to name, and the language names that pick each one by themselves.
COURSE_NAMES = {"es": ("Spanish", ("spanish", "español", "espanol", "castellano"))}
CODE = re.compile(r"^[a-z]{2,3}$")
FILE = re.compile(r"^u(\d{2})\.json$")
CEFR = ("A1", "A2", "B1")
KINDS = ("word", "phrase", "verb")
ITEM_KEYS = {"es", "en", "kind", "accept", "accept_en", "note", "gender"}
SENTENCE_KEYS = {"es", "en", "focus", "accept", "accept_en"}
LESSON_KEYS = {"id", "title", "notes", "items", "sentences"}
UNIT_KEYS = {"unit", "title", "cefr", "goal", "lessons"}
ARTICLES = ("el", "la", "los", "las", "un", "una", "unos", "unas", "l'", "le", "les", "der", "die", "das")
WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
LESSON_ID = r"^[a-z]{2,3}-u\d{2}-l\d{1,2}$"


def words(text: str) -> list[str]:
    """The words of a sentence as written (punctuation and numbers left out)."""
    return WORD.findall(text or "")


def core(es: str) -> str:
    """An item without its article and punctuation, lower case: "el café" -> "café", "¿Cómo estás?" -> "cómo estás"."""
    ws = [w.lower() for w in words(es)]
    if len(ws) > 1 and ws[0] in ARTICLES:
        ws = ws[1:]
    return " ".join(ws)


# ---------------------------------------------------------------------------------------------
# Checking a unit file (pure: tested directly, and run over every real file by the tests)
# ---------------------------------------------------------------------------------------------
def _text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _texts(v) -> bool:
    return isinstance(v, list) and all(_text(x) for x in v)


def check_unit(data, code: str, filename: str, seen_ids: set | None = None) -> list[tuple[str, str]]:
    """Problems with one unit file, each (level, message):
        error   the engine can't use it: the unit is left out (a missing field, a bad id, a focus word that isn't in
                its sentence, an unknown field - usually a typo)
        rule    the README's rules, with a little slack (3-5 lessons, 6-12 items and sentences, notes 30-180 words,
                ¿...? and ¡...!, short sentences): the content test fails, the app still uses it
        advice  the README's exact numbers, and each item showing up in a sentence of its lesson or the next: worth a
                look, nothing fails
    seen_ids: lesson ids already used in the course (ids must be unique across it); this unit's are added."""
    out: list[tuple[str, str]] = []

    def err(msg): out.append(("error", f"{filename}: {msg}"))

    def rule(msg): out.append(("rule", f"{filename}: {msg}"))

    def advice(msg): out.append(("advice", f"{filename}: {msg}"))

    if not isinstance(data, dict):
        err("not a JSON object")
        return out
    m = FILE.match(filename)
    if not m:
        err("the file should be named uNN.json")
        return out
    nn = int(m.group(1))
    for k in sorted(set(data) - UNIT_KEYS):
        err(f"unknown field '{k}'")
    if not isinstance(data.get("unit"), int) or isinstance(data.get("unit"), bool) or not 1 <= data["unit"] <= 60:
        err("'unit' must be a number 1-60")
    elif data["unit"] != nn:
        err(f"'unit' is {data['unit']} but the file is u{nn:02d}.json")
    for k in ("title", "goal"):
        if not _text(data.get(k)):
            err(f"'{k}' is missing")
    if data.get("cefr") not in CEFR:
        err(f"'cefr' must be one of {', '.join(CEFR)}")
    lessons = data.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        err("'lessons' must be a list of lessons")
        return out
    if not 3 <= len(lessons) <= 5:
        rule(f"{len(lessons)} lessons (3-5)")
    seen_ids = seen_ids if seen_ids is not None else set()
    a1 = data.get("cefr") == "A1"
    for li, lesson in enumerate(lessons, 1):
        where = f"lesson {li}"
        if not isinstance(lesson, dict):
            err(f"{where} isn't an object")
            continue
        for k in sorted(set(lesson) - LESSON_KEYS):
            err(f"{where}: unknown field '{k}'")
        want = f"{code}-u{nn:02d}-l{li}"
        lid = lesson.get("id")
        if lid != want:
            err(f"{where}: id is {lid!r}, should be {want!r} (the unit and its place in the unit)")
        elif lid in seen_ids:
            err(f"{where}: id {lid} is used twice")
        else:
            seen_ids.add(lid)
            where = lid
        for k in ("title", "notes"):
            if not _text(lesson.get(k)):
                err(f"{where}: '{k}' is missing")
        if _text(lesson.get("notes")):
            n = len(lesson["notes"].split())
            if not 30 <= n <= 180:
                rule(f"{where}: the notes are {n} words (40-150)")
            elif not 40 <= n <= 150:
                advice(f"{where}: the notes are {n} words (40-150)")
            if re.search(r"<[a-zA-Z/]", lesson["notes"]):
                rule(f"{where}: the notes have HTML in them (plain text, **bold** and line breaks only)")
        items, sentences = lesson.get("items"), lesson.get("sentences")
        if not isinstance(items, list) or not items:
            err(f"{where}: 'items' must be a list")
            items = []
        if not isinstance(sentences, list) or not sentences:
            err(f"{where}: 'sentences' must be a list")
            sentences = []
        if items and not 6 <= len(items) <= 12:
            rule(f"{where}: {len(items)} items (6-12)")
        if sentences and not 6 <= len(sentences) <= 12:
            rule(f"{where}: {len(sentences)} sentences (6-12)")
        seen_es = set()
        for ii, item in enumerate(items, 1):
            what = f"{where} item {ii}"
            if not isinstance(item, dict):
                err(f"{what} isn't an object")
                continue
            for k in sorted(set(item) - ITEM_KEYS):
                err(f"{what}: unknown field '{k}'")
            if not _text(item.get("es")) or not _text(item.get("en")):
                err(f"{what}: 'es' and 'en' are both needed")
                continue
            what = f"{where} item '{item['es']}'"
            if item.get("kind") not in KINDS:
                err(f"{what}: 'kind' must be word, phrase or verb")
            for k in ("accept", "accept_en"):
                if k in item and not _texts(item[k]):
                    err(f"{what}: '{k}' must be a list of answers")
            if "note" in item and not _text(item["note"]):
                err(f"{what}: 'note' is empty")
            if "gender" in item and item["gender"] not in ("m", "f"):
                err(f"{what}: 'gender' must be m or f")
            if item["es"].strip().lower() in seen_es:
                advice(f"{what}: twice in the lesson")
            seen_es.add(item["es"].strip().lower())
        for si, s in enumerate(sentences, 1):
            what = f"{where} sentence {si}"
            if not isinstance(s, dict):
                err(f"{what} isn't an object")
                continue
            for k in sorted(set(s) - SENTENCE_KEYS):
                err(f"{what}: unknown field '{k}'")
            if not _text(s.get("es")) or not _text(s.get("en")):
                err(f"{what}: 'es' and 'en' are both needed")
                continue
            what = f"{where} sentence '{s['es']}'"
            for k in ("accept", "accept_en"):
                if k in s and not _texts(s[k]):
                    err(f"{what}: '{k}' must be a list of answers")
            if "focus" in s:
                if not isinstance(s["focus"], str) or s["focus"].lower() not in [w.lower() for w in words(s["es"])]:
                    err(f"{what}: the focus {s.get('focus')!r} isn't one of its words")
                elif s["focus"] not in words(s["es"]):
                    advice(f"{what}: the focus {s['focus']!r} is written differently in the sentence (the sentence's way is used)")
            if code == "es":
                if "?" in s["es"] and "¿" not in s["es"]:
                    rule(f"{what}: a question opens with ¿")
                if "!" in s["es"] and "¡" not in s["es"]:
                    rule(f"{what}: an exclamation opens with ¡")
            n = len(words(s["es"]))
            if n > (12 if a1 else 16):
                rule(f"{what}: {n} words (up to {10 if a1 else 14} at {data.get('cefr')})")
            elif n > (10 if a1 else 14):
                advice(f"{what}: {n} words (up to {10 if a1 else 14} at {data.get('cefr')})")
    # each item shows up in a sentence of its lesson or the next (verbs are left out: their forms change)
    for li, lesson in enumerate(lessons):
        if not isinstance(lesson, dict) or not isinstance(lesson.get("items"), list):
            continue
        said = []
        for later in lessons[li:li + 2]:
            if isinstance(later, dict) and isinstance(later.get("sentences"), list):
                said += [" ".join(w.lower() for w in words(s.get("es", ""))) for s in later["sentences"] if isinstance(s, dict)]
        for item in lesson["items"]:
            if not isinstance(item, dict) or not _text(item.get("es")) or item.get("kind") == "verb":
                continue
            c = core(item["es"])
            stem = c[:-1] if len(c) > 4 and c[-1] in "aeo" else c
            if stem and not any(re.search(r"(?<!\w)" + re.escape(stem), line) for line in said):
                advice(f"{lesson.get('id')}: '{item['es']}' isn't in a sentence of this lesson or the next")
    return out


def errors_only(problems):
    return [msg for level, msg in problems if level == "error"]


# ---------------------------------------------------------------------------------------------
# Loading (once; cached)
# ---------------------------------------------------------------------------------------------
def gap_word(sentence: dict, items: list[dict]) -> str:
    """The word a sentence's cloze hides: its focus; else a word of it that's one of the lesson's items (the longest);
    else its longest word."""
    ws = words(sentence["es"])
    if sentence.get("focus"):
        return next((w for w in ws if w == sentence["focus"]), None) or next(
            (w for w in ws if w.lower() == sentence["focus"].lower()), sentence["focus"])     # (as the sentence writes it)
    lower = {w.lower(): w for w in reversed(ws)}       # (the first time it's written)
    for c in sorted((core(i["es"]) for i in items), key=len, reverse=True):
        if c and " " not in c and c in lower:
            return lower[c]
    return max(ws, key=len) if ws else sentence["es"]


def cloze_front(es: str, gap: str) -> str:
    """"Hola, me llamo Ana." + "llamo" -> "Hola, me {{llamo}} Ana." (the first time it's a whole word)."""
    m = re.search(r"(?<![\w])" + re.escape(gap) + r"(?![\w])", es)
    return es[:m.start()] + "{{" + gap + "}}" + es[m.end():] if m else es + " {{" + gap + "}}"


def _prepare(data: dict, code: str) -> dict:
    unit = {k: data[k] for k in ("unit", "title", "cefr", "goal")}
    unit["lessons"] = []
    for lesson in data["lessons"]:
        items = [dict(i) for i in lesson["items"]]
        sentences = [{**s, "gap": gap_word(s, items)} for s in lesson["sentences"]]
        unit["lessons"].append({"id": lesson["id"], "title": lesson["title"], "notes": lesson["notes"], "unit": data["unit"],
                                "items": items, "sentences": sentences})
    return unit


def course_name(code: str) -> str:
    return COURSE_NAMES.get(code, (code.upper(), ()))[0]


@lru_cache(maxsize=8)
def _load(root: str) -> dict:
    courses = {}
    base = Path(root)
    if not base.is_dir():
        return courses
    for folder in sorted(p for p in base.iterdir() if p.is_dir() and CODE.match(p.name)):
        code, units, seen = folder.name, [], set()
        for f in sorted(folder.glob("u*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                log.warning("Course %s: %s left out - it isn't readable JSON (%s)", code, f.name, e)
                continue
            ids = set(seen)
            bad = errors_only(check_unit(data, code, f.name, ids))
            if bad:
                log.warning("Course %s: %s left out - %s", code, f.name, "; ".join(bad[:5]))
                continue
            if any(u["unit"] == data["unit"] for u in units):
                continue
            seen = ids
            units.append(_prepare(data, code))
        if not units:
            continue
        units.sort(key=lambda u: u["unit"])
        order = [lesson for u in units for lesson in u["lessons"]]
        courses[code] = {"code": code, "name": course_name(code), "units": units, "order": order,
                         "index": {lesson["id"]: i for i, lesson in enumerate(order)}}
    return courses


def courses() -> dict:
    """Every course, read once (start-up: main.py's lifespan) and kept."""
    return _load(str(COURSES_DIR))


def reload():
    _load.cache_clear()


def course_for_name(name: str | None) -> str | None:
    """The course a language picks by itself from its name ("Spanish", "español"), if there is one."""
    n = (name or "").strip().lower()
    return next((code for code, (_, names) in COURSE_NAMES.items() if n in names and code in courses()), None)


def course_exists(code: str | None):
    if code is not None and code not in courses():
        raise HTTPException(422, "There's no course for that language yet.")


def _summary(c: dict) -> dict:
    return {"code": c["code"], "name": c["name"], "units": len(c["units"]), "lessons": len(c["order"]),
            "levels": sorted({u["cefr"] for u in c["units"]}),
            "names": list(COURSE_NAMES.get(c["code"], ("", ()))[1])}       # (language names that pick it by themselves)


def find_lesson(lesson_id: str) -> tuple[dict, dict]:
    code = lesson_id.split("-", 1)[0]
    c = courses().get(code)
    if not c or lesson_id not in c["index"]:
        raise HTTPException(404, "There's no such lesson.")
    return c, c["order"][c["index"][lesson_id]]


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------
@router.get("/language/courses")
def list_courses():
    return [_summary(c) for c in courses().values()]


def _progress(conn, language_id: int) -> dict:
    rows = conn.execute("""
        SELECT lesson_id, count(*)::int AS times, max(score)::int AS best, min(done_at) AS first_done, max(done_at) AS last_done,
               (array_agg(score ORDER BY done_at DESC))[1]::int AS last_score
        FROM lang_lesson_runs WHERE language_id = %s GROUP BY lesson_id""", (language_id,)).fetchall()
    return {r["lesson_id"]: r for r in rows}


def _brief(lesson: dict, unit: dict) -> dict:
    return {"id": lesson["id"], "title": lesson["title"], "unit": unit["unit"], "unit_title": unit["title"]}


def _next(c: dict, done: dict) -> dict | None:
    """The first lesson not done yet (in course order)."""
    for u in c["units"]:
        for lesson in u["lessons"]:
            if lesson["id"] not in done:
                return _brief(lesson, u)
    return None


def _language(conn, language_id: int) -> dict:
    return found(conn.execute("SELECT language_id, name, voice, course FROM lang_languages WHERE language_id = %s",
                              (language_id,)).fetchone(), "Language")


@router.get("/language/languages/{language_id}/course")
def language_course(language_id: int):
    with db() as conn:
        lang = _language(conn, language_id)
        done = _progress(conn, language_id)
    available = list_courses()
    c = courses().get(lang["course"]) if lang["course"] else None
    if not c:
        return {"language": lang, "course": None, "missing": lang["course"], "available": available,
                "suggested": course_for_name(lang["name"])}
    units, prev_done, all_done = [], True, 0
    for u in c["units"]:
        lessons = []
        for lesson in u["lessons"]:
            p = done.get(lesson["id"])
            lessons.append({"id": lesson["id"], "title": lesson["title"], "items": len(lesson["items"]),
                            "done": p is not None, "best": p and p["best"], "last_score": p and p["last_score"],
                            "times": p["times"] if p else 0, "last_done": p and p["last_done"],
                            "unlocked": prev_done or p is not None})
            prev_done = p is not None
        n = sum(1 for x in lessons if x["done"])
        all_done += n
        units.append({"unit": u["unit"], "title": u["title"], "cefr": u["cefr"], "goal": u["goal"], "lessons": lessons,
                      "done": n, "total": len(lessons)})
    nxt = _next(c, done)
    if nxt:
        for u in units:
            for x in u["lessons"]:
                x["next"] = x["id"] == nxt["id"]
    return {"language": lang, "course": _summary(c), "units": units, "next": nxt, "done": all_done, "total": len(c["order"]),
            "available": available}


@router.get("/language/course/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    c, lesson = find_lesson(lesson_id)
    i = c["index"][lesson_id]
    unit = next(u for u in c["units"] if u["unit"] == lesson["unit"])
    earlier, seen = [], {core(x["es"]) for x in lesson["items"]}
    for before in reversed(c["order"][:i]):             # (nearest first: the words you met lately)
        for x in before["items"]:
            k = core(x["es"])
            if k not in seen:
                seen.add(k)
                earlier.append({"es": x["es"], "en": x["en"], "kind": x["kind"]})
    return {"course": c["code"], "course_name": c["name"], **lesson,
            "unit_title": unit["title"], "cefr": unit["cefr"], "goal": unit["goal"],
            "number": unit["lessons"].index(lesson) + 1, "of": len(unit["lessons"]),
            "earlier": earlier[:120],
            "next": _brief(c["order"][i + 1], next(u for u in c["units"] if u["unit"] == c["order"][i + 1]["unit"]))
            if i + 1 < len(c["order"]) else None}


class LessonDone(BaseModel):
    score: int = Field(ge=0, le=100)
    mistakes: int = Field(0, ge=0, le=1000)
    seconds: int = Field(0, ge=0, le=14400)


def lesson_cards(lesson: dict, code: str) -> list[dict]:
    """The cards a finished lesson puts in the deck: each item a word card (an example sentence of the lesson with it,
    if there is one), each sentence a cloze card on its gap word. Pure (tested directly)."""
    tag = [f"{code}-u{lesson['unit']:02d}"]
    cards = []
    for item in lesson["items"]:
        c = core(item["es"])
        example = next((s for s in lesson["sentences"] if c and re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)",
                                                                           " ".join(words(s["es"])).lower())), None)
        cards.append({"kind": "word", "front": item["es"].strip(), "back": item["en"].strip(),
                      "example": example and example["es"], "example_meaning": example and example["en"],
                      "notes": item.get("note"), "tags": tag})
    for s in lesson["sentences"]:
        cards.append({"kind": "cloze", "front": cloze_front(s["es"].strip(), s["gap"]), "back": s["en"].strip(),
                      "example": None, "example_meaning": None, "notes": None, "tags": tag})
    return cards


@router.post("/language/languages/{language_id}/lessons/{lesson_id}/done", status_code=201)
def lesson_done(language_id: int, lesson_id: str, body: LessonDone):
    with db() as conn:
        lang = _language(conn, language_id)
        c, lesson = find_lesson(lesson_id)
        if lang["course"] != c["code"]:
            raise HTTPException(422, f"{lang['name']} doesn't follow the {c['name']} course.")
        first = not conn.execute("SELECT 1 FROM lang_lesson_runs WHERE language_id = %s AND lesson_id = %s",
                                 (language_id, lesson_id)).fetchone()
        added = []
        for card in lesson_cards(lesson, c["code"]):
            row = conn.execute("""
                INSERT INTO lang_cards (language_id, kind, front, back, example, example_meaning, notes, tags, lesson_id)
                VALUES (%(language_id)s, %(kind)s, %(front)s, %(back)s, %(example)s, %(example_meaning)s, %(notes)s, %(tags)s,
                        %(lesson_id)s)
                ON CONFLICT (language_id, kind, lower(front)) DO NOTHING RETURNING card_id""",
                {**card, "language_id": language_id, "lesson_id": lesson_id}).fetchone()
            if row:
                added.append({"card_id": row["card_id"], "kind": card["kind"], "front": card["front"]})
        run = conn.execute("""
            INSERT INTO lang_lesson_runs (language_id, lesson_id, unit, title, score, mistakes, seconds, cards_added)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING run_id, done_at""",
            (language_id, lesson_id, lesson["unit"], lesson["title"], body.score, body.mistakes, body.seconds, len(added))).fetchone()
        done = _progress(conn, language_id)
    unit = next(u for u in c["units"] if u["unit"] == lesson["unit"])
    return {"run_id": run["run_id"], "done_at": run["done_at"], "lesson_id": lesson_id, "score": body.score,
            "first_time": first, "added": len(added), "words": sum(1 for a in added if a["kind"] == "word"),
            "sentences": sum(1 for a in added if a["kind"] == "cloze"), "cards": added[:40],
            "unit_done": all(x["id"] in done for x in unit["lessons"]), "next": _next(c, done)}
