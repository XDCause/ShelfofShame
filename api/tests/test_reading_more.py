"""Reading, more: the year in review, private tags and your own challenges."""
from datetime import date

from app.reading_more import length_of, year_facts


def add(client, **book):
    r = client.post("/api/reading/books", json={"title": "A Book", **book})
    assert r.status_code == 201, r.text
    return r.json()


def test_length_buckets():
    assert [length_of(p) for p in (None, 120, 249, 250, 499, 500, 900)] == [None, "short", "short", "medium", "medium", "long", "long"]


def read(title, pages, finished, **more):
    return {"title": title, "author": more.get("author"), "pages": pages, "format": more.get("format"), "genres": more.get("genres", []),
            "rating": more.get("rating"), "finished_on": finished, "reread": more.get("reread", False)}


def test_year_facts_are_worked_out():
    reads = [read("Short", 200, date(2026, 1, 5), author="A", format="paper", rating=3, genres=["Fantasy"]),
             read("Long", 800, date(2026, 3, 9), author="A", format="ebook", rating=5, genres=["Fantasy", "Epic"]),
             read("Mid", 300, date(2026, 3, 20), author="B", rating=4, reread=True)]
    f = year_facts(reads, [{"day": date(2026, 1, 5), "pages": 100}, {"day": date(2026, 3, 9), "pages": 300}], date(2026, 12, 31), 2026)
    assert (f["books"], f["pages"], f["pages_read"], f["rereads"]) == (3, 1300, 400, 1)
    assert [m["books"] for m in f["by_month"]][:3] == [1, 0, 2] and f["by_month"][2]["pages"] == 300
    assert [(x["label"], x["books"]) for x in f["by_length"]] == [("short", 1), ("medium", 1), ("long", 1)]
    assert f["longest"]["title"] == "Long" and f["favourite"]["title"] == "Long" and f["average_rating"] == 4.0
    assert f["genres"][0] == {"label": "Fantasy", "books": 2} and f["authors"][0] == {"label": "A", "books": 2}
    assert f["pages_a_day"] == round(400 / 365, 1) and f["five_stars"] == 1
    assert year_facts([], [], date(2026, 6, 1), 2026)["favourite"] is None


def test_review_endpoint(client):
    today = date.today()
    a = add(client, title="One", author="Ann", pages=300, format="paper", status="finished", rating=5, genres=["Crime"])
    add(client, title="Two", author="Ann", pages=120, status="finished")
    add(client, title="Wanted", status="want")
    r = client.get("/api/reading/review").json()
    assert r["year"] == today.year and r["books"] == 2 and r["pages"] == 420 and r["new_authors"] == 1
    assert r["favourite"]["book_id"] == a["book_id"] and today.year in r["years"]
    assert client.get("/api/reading/review?year=2001").json()["books"] == 0
    assert client.get("/api/reading/review?year=1800").status_code == 422


def test_tags_and_filter(client):
    a = add(client, title="Slow one")
    b = add(client, title="Quick one")
    r = client.patch(f"/api/reading/books/{a['book_id']}", json={"tags": [" slow start ", "dark themes", "Slow Start"]})
    assert r.json()["tags"] == ["slow start", "dark themes"]
    client.patch(f"/api/reading/books/{b['book_id']}", json={"tags": ["dark themes"]})
    assert client.get("/api/reading/tags").json() == [{"tag": "dark themes", "books": 2}, {"tag": "slow start", "books": 1}]
    assert [x["title"] for x in client.get("/api/reading/books?tag=SLOW START").json()["books"]] == ["Slow one"]
    assert len(client.get("/api/reading/books?tag=dark themes").json()["books"]) == 2


def test_challenges(client):
    big = add(client, title="Big", pages=600, status="finished", genres=["Fantasy"])
    add(client, title="Small", pages=100, status="finished")
    tagged = add(client, title="Tagged", pages=200, status="finished")
    client.patch(f"/api/reading/books/{tagged['book_id']}", json={"tags": ["new country"]})
    pages = client.post("/api/reading/challenges", json={"name": "Big books", "target": 2, "rule": "pages_over", "rule_value": "500"}).json()
    assert (pages["done"], pages["percent"], pages["reached"]) == (1, 50, False)
    by_tag = client.post("/api/reading/challenges", json={"name": "Countries", "target": 1, "rule": "tag", "rule_value": "New Country"}).json()
    assert by_tag["done"] == 1 and by_tag["reached"]
    genre = client.post("/api/reading/challenges", json={"name": "Fantasy", "target": 5, "rule": "genre", "rule_value": "fantasy",
                                                         "year": 2001}).json()
    assert genre["done"] == 0                                    # finished this year, not in 2001
    manual = client.post("/api/reading/challenges", json={"name": "By hand", "target": 2, "rule": "manual"}).json()
    assert manual["done"] == 0
    assert client.put(f"/api/reading/challenges/{pages['challenge_id']}/books/{big['book_id']}").status_code == 409
    ticked = client.put(f"/api/reading/challenges/{manual['challenge_id']}/books/{big['book_id']}").json()
    assert ticked["done"] == 1 and ticked["books"][0]["title"] == "Big"
    assert client.delete(f"/api/reading/challenges/{manual['challenge_id']}/books/{big['book_id']}").json()["done"] == 0
    assert client.put(f"/api/reading/challenges/{manual['challenge_id']}/books/99999").status_code == 404
    assert client.patch(f"/api/reading/challenges/{pages['challenge_id']}", json={"rule_value": "100"}).json()["done"] == 2
    assert client.patch(f"/api/reading/challenges/{pages['challenge_id']}", json={"rule_value": "lots"}).status_code == 422
    assert len(client.get("/api/reading/challenges").json()) == 4
    # a rule needs its word; a book going takes its tick with it
    assert client.post("/api/reading/challenges", json={"name": "X", "target": 1, "rule": "tag"}).status_code == 422
    assert client.delete(f"/api/reading/challenges/{pages['challenge_id']}").status_code == 204
    assert client.delete(f"/api/reading/challenges/{pages['challenge_id']}").status_code == 404
