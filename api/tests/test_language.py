"""Language learning: the FSRS scheduler's sums (srs.py), pasting cards, languages, cards, the review queue and answers
(with Undo), the study log, input hours and milestones, resources, the can-do list, the dashboard, stats, and the
parts other pages show (activity, calendar, goals, exports)."""
from datetime import datetime, timedelta, timezone

import pytest

from app import srs
from app.db import db
from app.language_cards import parse_lines

NOW = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- the scheduler (pure)
def test_a_new_card_learns_in_steps_then_graduates():
    new = {"state": "new"}
    again = srs.review(new, srs.AGAIN, NOW)
    assert again["state"] == "learning" and again["due"] == NOW + timedelta(minutes=1) and again["interval_days"] == 0
    good = srs.review(new, srs.GOOD, NOW)
    assert good["state"] == "learning" and good["due"] == NOW + timedelta(minutes=10)
    assert good["stability"] == pytest.approx(srs.W[2])
    # a second Good the same sitting: out of learning, days away
    later = NOW + timedelta(minutes=10)
    second = srs.review({**good, "last_review": NOW}, srs.GOOD, later)
    assert second["state"] == "review" and second["interval_days"] >= 1
    # Easy on a brand-new card skips learning
    easy = srs.review(new, srs.EASY, NOW)
    assert easy["state"] == "review" and easy["interval_days"] == round(srs.W[3])


def test_review_intervals_grow_and_keep_their_order():
    card = {"state": "review", "stability": 10.0, "difficulty": 5.0, "reps": 4, "lapses": 0,
            "last_review": NOW - timedelta(days=10)}
    hard, good, easy = (srs.review(card, g, NOW) for g in (srs.HARD, srs.GOOD, srs.EASY))
    assert hard["interval_days"] <= good["interval_days"] < easy["interval_days"]
    assert good["stability"] > 10 and good["interval_days"] > 10       # remembered at R = 0.9: it grows
    assert good["difficulty"] == pytest.approx(5.0, abs=0.2)            # Good barely moves difficulty
    assert hard["difficulty"] > good["difficulty"] > easy["difficulty"]
    # forgotten: shorter memory (not reset to zero), a lapse, relearning in a minute
    again = srs.review(card, srs.AGAIN, NOW)
    assert again["state"] == "relearning" and again["lapses"] == 1 and 0.1 <= again["stability"] < 10
    back = srs.review({**again, "last_review": NOW}, srs.GOOD, NOW + timedelta(minutes=1))
    assert back["state"] == "review" and back["interval_days"] >= 1


def test_retrievability_and_intervals():
    assert srs.retrievability(0, 5) == 1
    assert srs.retrievability(5, 5) == pytest.approx(0.9)               # stability: the day R reaches 90%
    assert srs.interval_days(7.4) == 7 and srs.interval_days(0.2) == 1 and srs.interval_days(1e9) == srs.MAX_DAYS
    # remembering an overdue card (lower R) grows its memory more
    on_time = srs.recall_stability(5, 10, srs.retrievability(10, 10), srs.GOOD)
    overdue = srs.recall_stability(5, 10, srs.retrievability(30, 10), srs.GOOD)
    assert overdue > on_time
    with pytest.raises(ValueError):
        srs.review({"state": "new"}, 5, NOW)


def test_preview_labels():
    p = srs.preview({"state": "new"}, NOW)
    assert p[1] == "1m" and p[2] == "5m" and p[3] == "10m" and p[4].endswith("d")
    mature = srs.preview({"state": "review", "stability": 200.0, "difficulty": 4.0, "last_review": NOW - timedelta(days=200)}, NOW)
    assert mature[4].endswith(("mo", "y"))


def test_pasted_lines():
    cards, bad = parse_lines("hola - hello\n# a comment\n\nperro\tdog\ngato = cat\nAyer {{fui}} al cine; Yesterday I went\n"
                             "just a word\nel coche – the car\n - nothing first")
    assert [(c["kind"], c["front"], c["back"]) for c in cards] == [
        ("word", "hola", "hello"), ("word", "perro", "dog"), ("word", "gato", "cat"),
        ("cloze", "Ayer {{fui}} al cine", "Yesterday I went"), ("word", "el coche", "the car")]
    assert bad == ["just a word", "- nothing first"]


# ---------------------------------------------------------------- the API
def language(client, name="Spanish", **extra):
    r = client.post("/api/language/languages", json={"name": name, "voice": "es-ES", "level": "A2", "goal_level": "B1",
                                                      "daily_minutes": 30, "new_per_day": 3, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def card(client, lang, front, back, **extra):
    r = client.post("/api/language/cards", json={"language_id": lang["language_id"], "front": front, "back": back, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_languages(client):
    es = language(client)
    assert es["cards"] == 0 and es["input_hours"] == 0 and es["active"]
    assert client.post("/api/language/languages", json={"name": " spanish "}).status_code == 409
    assert client.post("/api/language/languages", json={"name": "French", "level": "Z9"}).status_code == 422
    assert client.post("/api/language/languages", json={"name": "French", "voice": "not a tag!"}).status_code == 422
    fr = language(client, "French", voice="fr-FR", prior_input_hours=40)
    assert fr["input_hours"] == 40
    assert client.patch(f"/api/language/languages/{fr['language_id']}", json={"name": "Spanish"}).status_code == 409
    assert client.patch(f"/api/language/languages/{fr['language_id']}", json={"daily_minutes": None}).status_code == 422
    r = client.patch(f"/api/language/languages/{fr['language_id']}", json={"active": False, "level": "B1"})
    assert r.json()["level"] == "B1" and not r.json()["active"]
    assert [lang["name"] for lang in client.get("/api/language/languages").json()] == ["Spanish", "French"]
    assert client.delete(f"/api/language/languages/{fr['language_id']}").status_code == 204
    assert client.delete(f"/api/language/languages/{fr['language_id']}").status_code == 404
    lists = client.get("/api/language/lists").json()
    assert "Listening" in lists["input_activities"] and lists["milestones"][0]["hours"] == 50 and len(lists["cando"]) >= 18


def test_cards_and_bulk(client):
    es = language(client)
    c = card(client, es, "el perro", "the dog", example="El perro ladra.", tags=["Animals", "animals", "a1"])
    assert c["kind"] == "word" and c["state"] == "new" and c["tags"] == ["animals", "a1"]
    cloze = card(client, es, "Ayer {{fui::ir}} al cine", "Yesterday I went to the cinema")
    assert cloze["kind"] == "cloze"
    assert client.post("/api/language/cards", json={"language_id": es["language_id"], "kind": "cloze", "front": "no braces",
                                                    "back": "x"}).status_code == 422
    assert client.post("/api/language/cards", json={"language_id": es["language_id"], "front": "El Perro", "back": "x"}).status_code == 409
    assert client.post("/api/language/cards", json={"language_id": 999999, "front": "a", "back": "b"}).status_code == 422
    assert client.post("/api/language/cards", json={"language_id": es["language_id"], "front": "a", "back": "b",
                                                    "tags": ["two words"]}).status_code == 422
    r = client.post("/api/language/cards/bulk", json={"language_id": es["language_id"], "text": "el gato - the cat\nel perro - dog\n"
                                                      "el gato - again\nnonsense", "tags": ["animals"]})
    assert r.status_code == 201 and r.json() == {"added": 1, "skipped": ["el perro", "el gato"], "unreadable": ["nonsense"]}
    assert len(client.get(f"/api/language/cards?language_id={es['language_id']}").json()) == 3
    assert [x["front"] for x in client.get("/api/language/cards?q=CAT").json()] == ["el gato"]
    assert len(client.get("/api/language/cards?tag=animals").json()) == 2
    # edit, suspend, reset
    r = client.patch(f"/api/language/cards/{c['card_id']}", json={"back": "the dog (m.)", "suspended": True})
    assert r.json()["back"] == "the dog (m.)" and r.json()["suspended"]
    assert [x["card_id"] for x in client.get("/api/language/cards?state=suspended").json()] == [c["card_id"]]
    assert client.patch(f"/api/language/cards/{c['card_id']}", json={"front": "el gato"}).status_code == 409
    assert client.patch(f"/api/language/cards/{c['card_id']}", json={"front": None}).status_code == 422
    assert client.get(f"/api/language/cards/{c['card_id']}").json()["history"] == []
    assert client.delete(f"/api/language/cards/{c['card_id']}").status_code == 204
    assert client.get(f"/api/language/cards/{c['card_id']}").status_code == 404


def test_review_queue_answers_and_undo(client):
    es = language(client)                                        # 3 new cards a day
    cards = [card(client, es, f"palabra {i}", f"word {i}") for i in range(5)]
    q = client.get(f"/api/language/review?language_id={es['language_id']}").json()
    assert [c["card_id"] for c in q["cards"]] == [c["card_id"] for c in cards[:3]] and q["new_left"] == 3
    assert q["cards"][0]["next"] == {"1": "1m", "2": "5m", "3": "10m", "4": "15d"}
    first = cards[0]["card_id"]
    r = client.post(f"/api/language/cards/{first}/review", json={"grade": 3, "mode": "type", "seconds": 8})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["again_today"] and a["when"] == "10m" and a["card"]["state"] == "learning"
    q = client.get(f"/api/language/review?language_id={es['language_id']}").json()
    assert q["new_left"] == 2 and q["cards"][0]["card_id"] == first        # (learning, due within 20 minutes: first)
    # Easy graduates it; undo puts it back to learning
    r = client.post(f"/api/language/cards/{first}/review", json={"grade": 4}).json()
    assert r["card"]["state"] == "review" and not r["again_today"] and r["card"]["learned_on"]
    undone = client.post(f"/api/language/reviews/{r['review_id']}/undo")
    assert undone.status_code == 200 and undone.json()["state"] == "learning" and undone.json()["learned_on"] is None
    assert client.post(f"/api/language/reviews/{a['review_id']}/undo").status_code == 200     # and the first answer too
    assert client.get(f"/api/language/cards/{first}").json()["state"] == "new"
    assert client.post(f"/api/language/reviews/{a['review_id']}/undo").status_code == 404
    # a card due from an earlier day
    with db() as conn:
        conn.execute("""UPDATE lang_cards SET state = 'review', stability = 4, difficulty = 5, reps = 3,
                        last_review = now() - interval '5 days', due = now() - interval '1 day' WHERE card_id = %s""",
                     (cards[4]["card_id"],))
    q = client.get(f"/api/language/review?language_id={es['language_id']}").json()
    assert cards[4]["card_id"] in [c["card_id"] for c in q["cards"]]
    r = client.post(f"/api/language/cards/{cards[4]['card_id']}/review", json={"grade": 1, "mode": "listen"}).json()
    assert r["card"]["state"] == "relearning" and r["card"]["lapses"] == 1
    assert client.post(f"/api/language/cards/{first}/review", json={"grade": 5}).status_code == 422
    assert client.post(f"/api/language/cards/{first}/review", json={"grade": 3, "mode": "sing"}).status_code == 422
    assert client.post("/api/language/cards/999999/review", json={"grade": 3}).status_code == 404
    assert client.get("/api/language/review?language_id=999999").status_code == 404


def test_study_log_resources_and_input_hours(client):
    es = language(client, prior_input_hours=45)
    other = language(client, "Japanese", voice="ja-JP")
    book = client.post("/api/language/resources", json={"language_id": es["language_id"], "title": "Harry Potter y la piedra filosofal",
                                                         "kind": "Book", "level": "B1", "url": "https://example.com/hp"}).json()
    assert book["status"] == "Using" and book["minutes"] == 0
    assert client.post("/api/language/resources", json={"language_id": es["language_id"], "title": "x", "url": "ftp://x"}).status_code == 422
    r = client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "Reading", "minutes": 300,
                                                 "resource_id": book["resource_id"]})
    assert r.status_code == 201 and r.json()["resource"].startswith("Harry")
    tutor = client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "Tutor", "minutes": 60,
                                                     "with_whom": "Lucía", "notes": "Work on the subjunctive"}).json()
    client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "Writing", "minutes": 20})
    # a resource from another language doesn't fit
    assert client.post("/api/language/study", json={"language_id": other["language_id"], "activity": "Reading", "minutes": 5,
                                                    "resource_id": book["resource_id"]}).status_code == 422
    assert client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "Dancing", "minutes": 5}).status_code == 422
    assert client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "App", "minutes": 0}).status_code == 422
    assert [s["activity"] for s in client.get("/api/language/study?activity=Tutor").json()] == ["Tutor"]
    r = client.patch(f"/api/language/study/{tutor['study_id']}", json={"minutes": 45})
    assert r.json()["minutes"] == 45 and r.json()["with_whom"] == "Lucía"
    assert client.patch(f"/api/language/study/{tutor['study_id']}", json={"activity": None}).status_code == 422
    assert client.get("/api/language/resources").json()[0]["minutes"] == 300
    # input: 45 before + 300 min reading + 45 min tutor = 50.75 h - past the first milestone (writing doesn't count)
    s = client.get(f"/api/language/summary?language_id={es['language_id']}").json()
    assert s["input_hours"] == pytest.approx(50.8)
    assert [m["hours"] for m in s["milestones"]["reached"]] == [50] and s["milestones"]["next"]["hours"] == 150
    assert s["minutes_today"] == 365 and s["streak"]["current"] == 1 and len(s["days"]) == 84
    assert len(s["recent"]) == 3
    assert client.delete(f"/api/language/resources/{book['resource_id']}").status_code == 204
    assert client.get("/api/language/study?activity=Reading").json()[0]["resource"] is None    # the time stays
    assert client.delete(f"/api/language/study/{tutor['study_id']}").status_code == 204
    assert client.get(f"/api/language/study/{tutor['study_id']}").status_code == 404


def test_summary_and_stats(client):
    s = client.get("/api/language/summary").json()
    assert s["languages"] == [] and s["due"] == 0 and s["retention"] is None and s["streak"]["current"] == 0
    es = language(client)
    for i in range(4):
        card(client, es, f"w{i}", f"m{i}")
    c = client.get(f"/api/language/review?language_id={es['language_id']}").json()["cards"][0]
    client.post(f"/api/language/cards/{c['card_id']}/review", json={"grade": 3, "seconds": 60})
    s = client.get("/api/language/summary").json()
    assert s["new"] == 2 and s["due"] == 1 and s["reviews_today"] == 1 and s["minutes_today"] == 1
    assert s["goal_day"] == 30 and s["goal_week"] == 210 and s["cards"] == 4
    st = client.get(f"/api/language/stats?language_id={es['language_id']}").json()
    assert st["states"] == {"new": 3, "learning": 1} and st["reviews"][0]["reviews"] == 1 and st["forecast"][0]["cards"] == 1
    assert client.get("/api/language/summary?language_id=999999").status_code == 404


def test_cando(client):
    es = language(client)
    items = client.get(f"/api/language/languages/{es['language_id']}/cando").json()
    assert items[0]["item"] == "a1-introduce" and items[0]["done_on"] is None
    r = client.put(f"/api/language/languages/{es['language_id']}/cando/a1-introduce", json={"done": True})
    assert r.json()[0]["done_on"]
    r = client.put(f"/api/language/languages/{es['language_id']}/cando/a1-introduce", json={"done": False})
    assert r.json()[0]["done_on"] is None
    assert client.put(f"/api/language/languages/{es['language_id']}/cando/z9-nope", json={"done": True}).status_code == 404
    assert client.put("/api/language/languages/999999/cando/a1-introduce", json={"done": True}).status_code == 404


def test_other_pages_see_it(client):
    es = language(client)
    c = card(client, es, "hola", "hello")
    client.post(f"/api/language/cards/{c['card_id']}/review", json={"grade": 4})
    client.post("/api/language/study", json={"language_id": es["language_id"], "activity": "Class", "minutes": 90})
    feed = client.get("/api/activity?limit=10").json()
    kinds = {a["kind"]: a for a in feed}
    assert kinds["langstudy"]["title"] == "Spanish: class" and "90 min" in kinds["langstudy"]["detail"]
    assert kinds["langreview"]["ref"] == es["language_id"] and "100% remembered" in kinds["langreview"]["detail"]
    goals = {g["key"] for g in client.get("/api/goals/sources").json()}
    assert {"language_minutes", "language_input", "language_reviews", "language_words"} <= goals
    assert client.post("/api/calendar/parse", json={"text": "Spanish class tomorrow 6pm"}).json()["hobby"] == "language"
    assert client.post("/api/calendar/parse", json={"text": "italki with Lucía at 7pm"}).json()["hobby"] == "language"
    for kind in ("language-cards", "language-study"):
        r = client.get(f"/api/export/{kind}.csv")
        assert r.status_code == 200 and ("hola" in r.text or "Class" in r.text)
