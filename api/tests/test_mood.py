"""Mood in the journal: one of five per page, a few words, by day for Home and the calendar."""


def page(client, day, mood=None, words=(), title="Day"):
    r = client.post("/api/journal", json={"title": title, "entry_date": day, "mood": mood, "mood_words": list(words)})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_page_has_a_mood_and_a_few_words(client):
    p = page(client, "2026-10-12", "good", ["  Proud", "tired", "proud", "Relaxed  "])
    assert (p["mood"], p["mood_words"]) == ("good", ["proud", "tired", "relaxed"])   # tidied, no repeats
    url = f"/api/journal/{p['page_id']}"
    assert client.patch(url, json={"mood": "ecstatic"}).status_code == 422
    assert client.patch(url, json={"mood_words": ["a", "b", "c", "d", "e", "f"]}).status_code == 422
    assert client.patch(url, json={"mood_words": ["x" * 25]}).status_code == 422
    cleared = client.patch(url, json={"mood": None, "mood_words": []}).json()
    assert (cleared["mood"], cleared["mood_words"]) == (None, [])


def test_the_list_shows_and_filters_by_mood_and_finds_mood_words(client):
    page(client, "2026-10-10", "rough", ["stressed"], title="Bad day")
    page(client, "2026-10-11", "great", title="Good day")
    page(client, "2026-10-12", title="No mood")
    listed = {p["title"]: p["mood"] for p in client.get("/api/journal").json()}
    assert listed == {"Bad day": "rough", "Good day": "great", "No mood": None}
    assert [p["title"] for p in client.get("/api/journal?mood=rough").json()] == ["Bad day"]
    assert [p["title"] for p in client.get("/api/journal?q=stressed").json()] == ["Bad day"]


def test_each_days_mood_for_home_and_the_calendar(client):
    page(client, "2026-10-06", "meh")
    later = page(client, "2026-10-07", "okay")
    page(client, "2026-10-07", None)                       # a page without a mood doesn't count
    client.patch(f"/api/journal/{later['page_id']}", json={"mood": "great"})
    days = client.get("/api/journal/moods?start=2026-10-01&end=2026-10-31").json()
    assert [(d["day"], d["mood"]) for d in days] == [("2026-10-06", "meh"), ("2026-10-07", "great")]
    cal = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").json()
    assert [d["mood"] for d in cal["moods"]] == ["meh", "great"]
    assert client.get("/api/journal/moods?start=2026-10-31&end=2026-10-01").status_code == 422
