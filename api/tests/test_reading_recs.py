"""Book suggestions: seeds from your shelves, what's picked from Open Library (faked - made-up
results in its layout), Want to read / Not interested, and when they're due a refresh."""
import pytest

from app import openlibrary, reading_recs


def doc(work, title, author, ratings=50, avg=4.3, cover=1, subjects=("Fantasy",), more_authors=(), year=2015, pages=400):
    return {"key": f"/works/{work}", "title": title, "author_name": [author, *more_authors], "first_publish_year": year,
            "number_of_pages_median": pages, "cover_i": cover, "isbn": [], "subject": list(subjects),
            "ratings_average": avg, "ratings_count": ratings}


BROWN = [
    doc("OL1W", "Red Rising", "Pierce Brown", 102),               # you have it
    doc("OL3W", "Dark Age", "Pierce Brown", 13, year=2019),
    doc("OL2W", "Iron Gold", "Pierce Brown", 24, year=2018),     # older: comes first
    doc("OL8W", "A Short Story", "Pierce Brown", 9, pages=40),     # too short
    doc("OL9W", "Sons of Ares", "Pierce Brown", 9, more_authors=["Rik Hoskin"]),   # a comic with others
    doc("OL10W", "An Early Novel", "Pierce Brown", 0, year=2005),  # nobody rated it: goes last
    doc("OL11W", "赤い夜明け", "Pierce Brown", 40, year=2016),      # a translation
    doc("OL4W", "The Red Rising Series Collection 5 Books Set", "Pierce Brown", 1),   # a box set
    doc("OL5W", "Light Bringer", "Pierce Brown", 7, cover=None),  # no cover
    doc("OL6W", "Star Wars - From a Certain Point of View", "Renée Ahdieh", 7, more_authors=["Pierce Brown"]),
    doc("OL7W", "Iron gold", "Pierce Brown", 2),                  # the same title again
]
FANTASY = [
    doc("OL20W", "Tiamat's Wrath", "James S. A. Corey", 55),
    doc("OL21W", "The Way of Kings", "Brandon Sanderson", 166),
    doc("OL22W", "Leviathan Wakes", "James S.A. Corey", 168),     # same author, more ratings: kept instead
    doc("OL23W", "Obscure Thing", "Nobody Much", 3),              # too few ratings
    doc("OL24W", "Skyward", "Brandon Sanderson", 90),
    doc("OL25W", "Dark Age", "Pierce Brown", 13),                 # an author you have
    doc("OL26W", "A Summary of The Way of Kings", "Study Books", 40),
]
SCIFI = [
    doc("OL30W", "Oathbringer", "Brandon Sanderson", 90),         # Sanderson is already under Fantasy
    doc("OL31W", "Hyperion", "Dan Simmons", 120),
]


@pytest.fixture
def ol(monkeypatch):
    asked = []

    def get(params):
        asked.append(params)
        q = params.get("q", "")
        if q.startswith('author:"Pierce Brown"'):
            return BROWN
        if q.startswith('subject:"fantasy"'):
            assert "juvenile fiction" in q                      # no YA in a fantasy search
            return FANTASY
        if q.startswith('subject:"science fiction"'):
            return SCIFI
        return []
    monkeypatch.setattr(openlibrary, "_get", get)
    return asked


def add(client, **book):
    r = client.post("/api/reading/books", json={"status": "finished", **book})
    assert r.status_code == 201, r.text
    return r.json()


def test_nothing_to_go_on_yet(client, ol):
    r = client.get("/api/reading/recommendations").json()
    assert (r["has_seeds"], r["stale"], r["sections"]) == (False, False, [])


def test_seeds_come_from_your_ratings_and_genres(client):
    add(client, title="Red Rising (Red Rising Saga, #1)", author="Pierce Brown", rating=5, genres=["Fantasy", "Science fiction"])
    add(client, title="Golden Son (Red Rising Saga, #2)", author="Pierce Brown", rating=5, genres=["Science fiction"])
    add(client, title="Meh Book", author="Someone Else", rating=3, genres=["Fantasy"])
    add(client, title="Gave Up", author="Another", status="dnf", genres=["Horror"])
    add(client, title="Cookbook", author="A Chef", status="want", genres=["Cooking"])
    from app.db import db
    with db() as conn:
        s = reading_recs.seeds(conn)
    assert s["authors"] == [{"name": "Pierce Brown", "seed": "Red Rising", "seed_rating": 5.0}]   # 3 stars isn't enough
    assert s["genres"] == ["Fantasy", "Science fiction"]        # 8 and 7.5 points; not Horror (dnf), Cooking too small


def test_refresh_picks_then_want_and_dismiss(client, ol):
    add(client, title="Red Rising (Red Rising Saga, #1)", author="Pierce Brown", rating=5, genres=["Fantasy", "Science fiction"], ol_work="OL1W")
    before = client.get("/api/reading/recommendations").json()
    assert before["has_seeds"] and before["stale"] and before["sections"] == []
    assert client.post("/api/reading/recommendations/refresh").status_code == 202     # runs as a background task
    r = client.get("/api/reading/recommendations").json()
    assert r["stale"] is False and r["refresh"]["error"] is None
    by_author, fantasy, scifi = r["sections"]
    assert (by_author["kind"], by_author["reason"], by_author["seed"], by_author["seed_rating"]) == ("author", "Pierce Brown", "Red Rising", 5.0)
    assert [b["title"] for b in by_author["books"]] == ["Iron Gold", "Dark Age", "An Early Novel"]
    assert by_author["books"][0]["cover_url"] == "https://covers.openlibrary.org/b/id/1-M.jpg"
    assert (fantasy["kind"], fantasy["reason"]) == ("genre", "Fantasy")
    assert [b["title"] for b in fantasy["books"]] == ["Leviathan Wakes", "The Way of Kings"]   # one per author, first seen order
    assert [b["title"] for b in scifi["books"]] == ["Hyperion"]                                # an author once on the page
    # Want to read: it's on your shelf, gone from the suggestions.
    book = client.post("/api/reading/recommendations/OL2W/want").json()
    assert (book["title"], book["status"], book["ol_work"], book["author"]) == ("Iron Gold", "want", "OL2W", "Pierce Brown")
    assert client.post("/api/reading/recommendations/OL2W/want").status_code == 404
    # Not interested: gone, and never picked again.
    assert client.post("/api/reading/recommendations/OL21W/dismiss").status_code == 204
    r = client.get("/api/reading/recommendations").json()
    assert [b["title"] for s in r["sections"] for b in s["books"]] == ["Dark Age", "An Early Novel", "Leviathan Wakes", "Hyperion"] and r["dismissed"] == 1
    client.post("/api/reading/recommendations/refresh")
    titles = [b["title"] for s in client.get("/api/reading/recommendations").json()["sections"] for b in s["books"]]
    assert "The Way of Kings" not in titles and "Iron Gold" not in titles and "Skyward" in titles
    # Bringing them back makes a refresh due.
    assert client.delete("/api/reading/recommendations/dismissed").status_code == 204
    r = client.get("/api/reading/recommendations").json()
    assert r["dismissed"] == 0 and r["stale"] is True
    assert client.post("/api/reading/recommendations/bad/want").status_code == 422


def test_a_book_added_another_way_drops_out(client, ol):
    add(client, title="Red Rising", author="Pierce Brown", rating=5, genres=["Fantasy"])
    client.post("/api/reading/recommendations/refresh")
    add(client, title="Iron Gold (Red Rising Saga, #4)", author="Pierce Brown", status="want")
    titles = [b["title"] for s in client.get("/api/reading/recommendations").json()["sections"] for b in s["books"]]
    assert "Iron Gold" not in titles and "Dark Age" in titles


def test_new_top_author_makes_it_stale(client, ol):
    add(client, title="Red Rising", author="Pierce Brown", rating=5, genres=["Fantasy"])
    client.post("/api/reading/recommendations/refresh")
    assert client.get("/api/reading/recommendations").json()["stale"] is False
    add(client, title="Project Hail Mary", author="Andy Weir", rating=4.5, genres=["Fantasy"])
    assert client.get("/api/reading/recommendations").json()["stale"] is True


def test_open_library_down_keeps_the_old_ones(client, ol, monkeypatch):
    add(client, title="Red Rising", author="Pierce Brown", rating=5, genres=["Fantasy"])
    client.post("/api/reading/recommendations/refresh")

    def down(params):
        raise openlibrary.BookError("Couldn't reach Open Library (ConnectTimeout).")
    monkeypatch.setattr(openlibrary, "_get", down)
    client.post("/api/reading/recommendations/refresh")
    r = client.get("/api/reading/recommendations").json()
    assert r["refresh"]["error"].startswith("Couldn't reach") and len(r["sections"]) == 2      # by Brown, Fantasy
