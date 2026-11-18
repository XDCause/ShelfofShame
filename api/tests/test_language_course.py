"""Language learning's built-in courses (language_course.py): checking a unit file, loading a course (a bad unit left
out, the rest kept), the course path with progress and unlocking, a lesson's content, a finished lesson (cards added,
skipped the second time, minutes, the feed, the goal), a language picking its course by name - on a tiny made-up
course. And every REAL course file (app/data/courses) checked against the README's rules: a bad content file fails here."""
import json
from pathlib import Path

import pytest

from app import language_course as lc

REAL = Path(lc.__file__).parent / "data" / "courses"


def _lesson(unit, n, items, sentences, notes="Some **notes**.\nA second line."):
    return {"id": f"es-u{unit:02d}-l{n}", "title": f"Lesson {unit}.{n}", "notes": notes, "items": items, "sentences": sentences}


def _unit(n, lessons, cefr="A1"):
    return {"unit": n, "title": f"Unit {n}", "cefr": cefr, "goal": f"Goal {n}.", "lessons": lessons}


TINY = {
    "u01.json": _unit(1, [
        _lesson(1, 1, [{"es": "hola", "en": "hello", "kind": "word"},
                       {"es": "buenos días", "en": "good morning", "kind": "phrase", "accept": ["buen día"], "note": "Until midday."}],
                [{"es": "Hola, me llamo Ana.", "en": "Hello, my name is Ana.", "focus": "llamo"},
                 {"es": "¡Buenos días, Carlos!", "en": "Good morning, Carlos!"}]),
        _lesson(1, 2, [{"es": "el café", "en": "the coffee", "kind": "word", "gender": "m"},
                       {"es": "ser", "en": "to be", "kind": "verb"}],
                [{"es": "El café es bueno.", "en": "The coffee is good."}]),
    ]),
    "u02.json": _unit(2, [
        _lesson(2, 1, [{"es": "la mesa", "en": "the table", "kind": "word"}],
                [{"es": "Hola, la mesa.", "en": "Hello, the table.", "accept_en": ["Hi, the table."]}]),
    ]),
    # a mistake: the focus isn't in its sentence -> unit 3 is left out, the rest still work
    "u03.json": _unit(3, [_lesson(3, 1, [{"es": "sí", "en": "yes", "kind": "word"}],
                                  [{"es": "Sí.", "en": "Yes.", "focus": "no"}])]),
    "u04.json": "{ not json",
}


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    folder = tmp_path / "es"
    folder.mkdir()
    for name, data in TINY.items():
        (folder / name).write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(lc, "COURSES_DIR", tmp_path)
    lc.reload()
    yield tmp_path
    lc.reload()


# ---------------------------------------------------------------- the checker and the loader (pure)
def test_checking_a_unit():
    good = TINY["u01.json"]
    assert lc.errors_only(lc.check_unit(good, "es", "u01.json")) == []
    rules = [m for lv, m in lc.check_unit(good, "es", "u01.json") if lv == "rule"]
    assert any("2 lessons (3-5)" in m for m in rules) and any("2 items (6-12)" in m for m in rules)
    assert any("notes are" in m for m in rules)
    bad = json.loads(json.dumps(good))
    bad["lessons"][1]["id"] = "es-u01-l1"
    bad["lessons"][0]["items"][0]["knd"] = "word"
    bad["lessons"][0]["sentences"][0]["focus"] = "llama"
    del bad["goal"]
    errors = lc.errors_only(lc.check_unit(bad, "es", "u01.json"))
    assert any("'goal' is missing" in e for e in errors)
    assert any("unknown field 'knd'" in e for e in errors)
    assert any("focus 'llama'" in e for e in errors)
    other_case = json.loads(json.dumps(good))
    other_case["lessons"][0]["sentences"][0]["focus"] = "Llamo"     # (another case: advice, and the sentence's way is used)
    assert lc.errors_only(lc.check_unit(other_case, "es", "u01.json")) == []
    assert any("should be 'es-u01-l2'" in e for e in errors)
    assert any("but the file is u02.json" in e for e in lc.errors_only(lc.check_unit(good, "es", "u02.json")))
    # ids are unique across the course
    seen = {"es-u01-l1"}
    assert any("used twice" in e for e in lc.errors_only(lc.check_unit(good, "es", "u01.json", seen)))
    # ¿...? and an item missing from every sentence
    q = _unit(1, [_lesson(1, 1, [{"es": "el perro", "en": "the dog", "kind": "word"}], [{"es": "Cómo estás?", "en": "How are you?"}])])
    found = lc.check_unit(q, "es", "u01.json")
    assert ("rule", "u01.json: es-u01-l1 sentence 'Cómo estás?': a question opens with ¿") in found
    assert any(lv == "advice" and "'el perro' isn't in a sentence" in m for lv, m in found)


def test_gap_words_and_cloze():
    items = [{"es": "el café", "en": "the coffee", "kind": "word"}, {"es": "es", "en": "is", "kind": "word"}]
    assert lc.gap_word({"es": "Hola, me llamo Ana.", "focus": "llamo"}, items) == "llamo"
    assert lc.gap_word({"es": "Muy bien, gracias.", "focus": "muy"}, items) == "Muy"
    assert lc.gap_word({"es": "El Café es bueno."}, items) == "Café"           # an item's word (the longest), as written
    assert lc.gap_word({"es": "Muy bien, gracias."}, items) == "gracias"       # else the longest word
    assert lc.cloze_front("Hola, me llamo Ana.", "llamo") == "Hola, me {{llamo}} Ana."
    assert lc.cloze_front("Es el es.", "es") == "Es el {{es}}."                # a whole word, case and all
    assert lc.core("el café") == "café" and lc.core("¿Cómo estás?") == "cómo estás" and lc.core("la") == "la"


def test_loading_leaves_a_bad_unit_out(tiny, caplog):
    courses = lc.courses()
    c = courses["es"]
    assert [u["unit"] for u in c["units"]] == [1, 2]                          # unit 3 (bad focus) and 4 (not JSON) left out
    assert [x["id"] for x in c["order"]] == ["es-u01-l1", "es-u01-l2", "es-u02-l1"]
    assert c["order"][0]["sentences"][1]["gap"] == "Buenos"                  # (no focus: an item's word)
    assert lc.course_for_name(" Español ") == "es" and lc.course_for_name("French") is None


# ---------------------------------------------------------------- the API
def spanish(client, **extra):
    r = client.post("/api/language/languages", json={"name": "Spanish", "voice": "es-MX", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_language_picks_its_course(client, tiny):
    assert client.get("/api/language/courses").json() == [{"code": "es", "name": "Spanish", "units": 2, "lessons": 3, "levels": ["A1"],
                                                              "names": ["spanish", "español", "espanol", "castellano"]}]
    es = spanish(client)
    assert es["course"] == "es"                                              # by its name
    fr = client.post("/api/language/languages", json={"name": "French"}).json()
    assert fr["course"] is None
    r = client.get(f"/api/language/languages/{fr['language_id']}/course").json()
    assert r["course"] is None and r["available"][0]["code"] == "es" and r["suggested"] is None
    assert client.patch(f"/api/language/languages/{fr['language_id']}", json={"course": "fr"}).status_code == 422   # no such course
    assert client.patch(f"/api/language/languages/{fr['language_id']}", json={"course": "ES!"}).status_code == 422
    assert client.patch(f"/api/language/languages/{fr['language_id']}", json={"course": "es"}).json()["course"] == "es"
    assert client.patch(f"/api/language/languages/{es['language_id']}", json={"course": None}).json()["course"] is None
    no = client.post("/api/language/languages", json={"name": "Español", "course": None}).json()   # (said none: none)
    assert no["course"] is None
    assert client.get("/api/language/languages/999999/course").status_code == 404


def test_the_course_path_and_a_lesson(client, tiny):
    es = spanish(client)
    path = client.get(f"/api/language/languages/{es['language_id']}/course").json()
    assert path["course"]["code"] == "es" and path["done"] == 0 and path["total"] == 3
    assert path["next"] == {"id": "es-u01-l1", "title": "Lesson 1.1", "unit": 1, "unit_title": "Unit 1"}
    first, second = path["units"][0]["lessons"]
    assert first["unlocked"] and first["next"] and not first["done"] and first["items"] == 2
    assert not second["unlocked"] and not second["next"]
    assert path["units"][0]["goal"] == "Goal 1." and path["units"][0]["total"] == 2

    lesson = client.get("/api/language/course/lessons/es-u01-l2").json()
    assert lesson["title"] == "Lesson 1.2" and lesson["unit"] == 1 and lesson["number"] == 2 and lesson["of"] == 2
    assert lesson["notes"].startswith("Some **notes**")
    assert lesson["sentences"][0]["gap"] == "café"
    assert [x["es"] for x in lesson["earlier"]] == ["hola", "buenos días"]    # wrong options come from earlier lessons
    assert lesson["next"]["id"] == "es-u02-l1"
    assert client.get("/api/language/course/lessons/es-u03-l1").status_code == 404     # (its unit was left out)
    assert client.get("/api/language/course/lessons/nonsense").status_code == 404


def test_finishing_a_lesson(client, tiny):
    es = spanish(client)
    lid = es["language_id"]
    # a card you'd added yourself is kept (and not added twice)
    client.post("/api/language/cards", json={"language_id": lid, "front": "Hola", "back": "hi"})
    r = client.post(f"/api/language/languages/{lid}/lessons/es-u01-l1/done", json={"score": 90, "mistakes": 1, "seconds": 300})
    assert r.status_code == 201, r.text
    done = r.json()
    assert done["first_time"] and done["added"] == 3 and done["words"] == 1 and done["sentences"] == 2
    assert done["next"]["id"] == "es-u01-l2" and not done["unit_done"]
    cards = {c["front"]: c for c in client.get(f"/api/language/cards?language_id={lid}").json()}
    assert cards["Hola, me {{llamo}} Ana."]["kind"] == "cloze" and cards["Hola, me {{llamo}} Ana."]["back"] == "Hello, my name is Ana."
    assert cards["¡{{Buenos}} días, Carlos!"]["tags"] == ["es-u01"]
    word = cards["buenos días"]
    assert word["back"] == "good morning" and word["notes"] == "Until midday." and word["example"] == "¡Buenos días, Carlos!"
    assert cards["Hola"]["back"] == "hi"
    # again: recorded, nothing added twice; the path moves on
    again = client.post(f"/api/language/languages/{lid}/lessons/es-u01-l1/done", json={"score": 100, "seconds": 120}).json()
    assert not again["first_time"] and again["added"] == 0
    path = client.get(f"/api/language/languages/{lid}/course").json()
    first, second = path["units"][0]["lessons"]
    assert first["done"] and first["best"] == 100 and first["last_score"] == 100 and first["times"] == 2
    assert second["unlocked"] and second["next"] and path["done"] == 1
    # the unit's last lesson: the unit is done
    client.post(f"/api/language/languages/{lid}/lessons/es-u01-l2/done", json={"score": 80})
    last = client.post(f"/api/language/languages/{lid}/lessons/es-u02-l1/done", json={"score": 75}).json()
    assert last["unit_done"] and last["next"] is None
    # 300 s + 120 s of lessons = 7 minutes studied today
    s = client.get(f"/api/language/summary?language_id={lid}").json()
    assert s["minutes_today"] == 7 and s["streak"]["current"] == 1
    # the feed, the goal
    feed = [a for a in client.get("/api/activity?limit=20").json() if a["kind"] == "langlesson"]
    assert len(feed) == 4 and feed[-1]["title"] == "Spanish lesson: Lesson 1.1" and "90%" in feed[-1]["detail"]
    assert "1 mistake" in feed[-1]["detail"] and "3 new cards" in feed[-1]["detail"]
    assert "language_lessons" in {g["key"] for g in client.get("/api/goals/sources").json()}
    # refused: junk, a language without the course, a lesson that isn't there
    assert client.post(f"/api/language/languages/{lid}/lessons/es-u01-l1/done", json={"score": 101}).status_code == 422
    assert client.post(f"/api/language/languages/{lid}/lessons/es-u09-l1/done", json={"score": 50}).status_code == 404
    assert client.post("/api/language/languages/999999/lessons/es-u01-l1/done", json={"score": 50}).status_code == 404
    fr = client.post("/api/language/languages", json={"name": "French"}).json()
    assert client.post(f"/api/language/languages/{fr['language_id']}/lessons/es-u01-l1/done", json={"score": 50}).status_code == 422


# ---------------------------------------------------------------- the real content
def _real_files():
    return sorted(REAL.glob("*/u*.json")) if REAL.is_dir() else []


def test_every_real_course_file_follows_the_rules():
    """Every course file the app ships: readable JSON, the fields the engine needs, ids unique across the course, each
    focus word in its sentence, and the README's rules (lessons, items and sentences a lesson, notes' length, ¿...?).
    (Advice - an item missing from the sentences, the README's exact word counts - isn't failed on.)"""
    problems = []
    for folder in sorted(p for p in REAL.iterdir() if p.is_dir()) if REAL.is_dir() else []:
        seen, units = set(), set()
        for f in sorted(folder.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except ValueError as e:
                problems.append(f"{folder.name}/{f.name}: not readable JSON ({e})")
                continue
            problems += [f"{folder.name}/{m}" for lv, m in lc.check_unit(data, folder.name, f.name, seen) if lv != "advice"]
            if isinstance(data, dict):
                if data.get("unit") in units:
                    problems.append(f"{folder.name}/{f.name}: unit {data.get('unit')} twice")
                units.add(data.get("unit"))
    assert not problems, f"{len(problems)} problems in the course files:\n" + "\n".join(problems[:60])


def test_the_real_courses_load_whole():
    """What the app reads at start-up: every real unit file is used (none left out)."""
    lc.reload()
    loaded = {(code, u["unit"]) for code, c in lc.courses().items() for u in c["units"]}
    files = {(f.parent.name, int(f.stem[1:])) for f in _real_files() if f.stem[1:].isdigit()}
    assert files <= loaded, f"left out: {sorted(files - loaded)}"
