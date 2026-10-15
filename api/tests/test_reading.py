"""Reading: books from Open Library (faked here - tests never call it), progress, quotes, the goal,
stats, and a Goodreads import (a made-up export in Goodreads' layout)."""
from datetime import date, timedelta

import pytest

from app import openlibrary

HAIL_MARY = {"key": "/works/OL21745884W", "title": "Project Hail Mary", "author_name": ["Andy Weir"],
             "first_publish_year": 2021, "number_of_pages_median": 496, "cover_i": 11200092,
             "isbn": ["0593135202", "9780593135204"], "subject": ["Science fiction", "Space flight", "nyt:hardcover"]}
DUNE = {"key": "/works/OL893415W", "title": "Dune", "author_name": ["Frank Herbert"], "first_publish_year": 1965,
        "number_of_pages_median": 604, "cover_i": 11481354, "isbn": [], "subject": ["Fiction, science fiction, general"]}


@pytest.fixture
def ol(monkeypatch):
    """A fake Open Library: searches by q / isbn / title, recording what was asked."""
    asked = []

    def get(params):
        asked.append(params)
        if "isbn" in params:
            return [HAIL_MARY] if params["isbn"] == "9780593135204" else []
        text = (params.get("q") or params.get("title") or "").lower()
        return [d for d in (HAIL_MARY, DUNE) if d["title"].lower().startswith(text[:4])]
    monkeypatch.setattr(openlibrary, "_get", get)
    return asked


def add(client, **book):
    r = client.post("/api/reading/books", json={"title": "A Book", **book})
    assert r.status_code == 201, r.text
    return r.json()


def test_isbns_and_genres():
    assert openlibrary.isbn13("0-593-13520-2") == "9780593135204"         # ISBN-10 -> 13
    assert openlibrary.isbn13('="9780593135204"') == "9780593135204"       # Goodreads' quoting
    assert openlibrary.isbn13("9780593135205") is None                     # wrong check digit
    assert openlibrary.isbn13("12345") is None
    assert openlibrary.genres_of(["Fiction, science fiction, general", "Magic", "History of Mars"]) == \
        ["Fantasy", "Science fiction", "History"]


def test_finding_a_book_by_title_or_isbn(client, ol):
    r = client.get("/api/reading/lookup?q=project hail").json()
    hit = r["results"][0]
    assert (hit["title"], hit["author"], hit["pages"], hit["ol_work"], hit["isbn"]) == \
        ("Project Hail Mary", "Andy Weir", 496, "OL21745884W", "9780593135204")
    assert hit["cover_url"] == "https://covers.openlibrary.org/b/id/11200092-M.jpg" and hit["genres"] == ["Science fiction"]
    assert hit["book_id"] is None
    r = client.get("/api/reading/lookup?q=978-0-593-13520-4").json()      # an ISBN (scanned or typed)
    assert r["isbn"] == "9780593135204" and ol[-1] == {"isbn": "9780593135204", "limit": 1}
    book = add(client, **{k: hit[k] for k in ("title", "author", "isbn", "ol_work", "cover_id", "pages", "year", "genres")})
    assert book["cover_url"].endswith("11200092-M.jpg") and book["status"] == "want"
    assert client.get("/api/reading/lookup?q=project hail").json()["results"][0]["book_id"] == book["book_id"]
    assert client.post("/api/reading/books", json={"title": "X", "isbn": "123"}).status_code == 422


def test_reading_a_book_page_by_page(client):
    book = add(client, title="Dune", pages=600)
    url = f"/api/reading/books/{book['book_id']}"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = client.post(f"{url}/progress", json={"page": 50, "logged_on": yesterday}).json()
    assert (r["status"], r["started_on"], r["current_page"], r["percent"]) == ("reading", yesterday, 50, 8)
    r = client.post(f"{url}/progress", json={"page": 170, "minutes": 90}).json()
    assert [entry["pages"] for entry in r["log"]] == [120, 50] and not r["at_the_end"]
    assert client.post(f"{url}/progress", json={"page": 700}).status_code == 422      # past the last page
    r = client.post(f"{url}/progress", json={"page": 600}).json()
    assert r["at_the_end"]
    client.delete(f"/api/reading/log/{r['log'][0]['log_id']}")                      # take it back
    assert client.get(url).json()["current_page"] == 170
    r = client.patch(url, json={"status": "finished", "rating": 5, "review": "Spice."}).json()
    assert (r["percent"], r["current_page"], r["finished_on"], r["rating"]) == (100, 600, date.today().isoformat(), 5)
    assert [entry["pages"] for entry in r["log"]] == [430, 120, 50]                # the rest counts as read today
    assert client.get("/api/reading/summary").json()["year"]["pages_read"] == 600
    r = client.patch(url, json={"status": "reading"}).json()                          # oops, not yet
    assert r["finished_on"] is None and r["status"] == "reading"
    client.delete(f"/api/reading/log/{r['log'][0]['log_id']}")
    assert client.get(url).json()["current_page"] == 170
    assert client.patch(url, json={"rating": 6}).status_code == 422
    assert client.patch(url, json={"rating": 3.3}).status_code == 422          # halves only
    assert client.patch(url, json={"rating": 3.5}).json()["rating"] == 3.5
    client.patch(url, json={"rating": 5})


def test_quotes(client):
    book = add(client, title="Dune", author="Frank Herbert")
    url = f"/api/reading/books/{book['book_id']}/quotes"
    client.post(url, json={"text": "Fear is the mind-killer.", "page": 8})
    r = client.post(url, json={"text": "The spice must flow."}).json()
    assert [q["text"] for q in r["quotes_list"]] == ["Fear is the mind-killer.", "The spice must flow."] and r["quotes"] == 2
    found = client.get("/api/reading/quotes?q=herbert").json()
    assert len(found) == 2 and found[0]["title"] == "Dune"
    assert client.delete(f"/api/reading/quotes/{found[0]['quote_id']}").status_code == 204
    assert len(client.get("/api/reading/quotes").json()) == 1


def test_the_goal_summary_and_stats(client):
    today = date.today()
    s = client.get("/api/reading/summary").json()
    assert s["goal"]["goal"] is None and s["reading"] == []
    add(client, title="Old one", pages=300, status="finished", rating=4)       # added as read: no log
    now = add(client, title="Now", pages=400)
    client.post(f"/api/reading/books/{now['book_id']}/progress", json={"page": 40})
    add(client, title="Next", status="want")
    s = client.put("/api/reading/goal", json={"books": 12}).json()
    g = s["goal"]
    assert (g["goal"], g["finished"], g["left"], g["year"]) == (12, 1, 11, today.year)
    assert g["on_pace"] == pytest.approx(12 * ((today - date(today.year, 1, 1)).days + 1) / (366 if today.year % 4 == 0 else 365), abs=0.1)
    assert [b["title"] for b in s["reading"]] == ["Now"] and s["week"]["pages"] == 40
    assert s["year"]["pages_read"] == 340 and s["counts"] == {"want": 1, "reading": 1, "finished": 1, "dnf": 0}
    assert s["streak"]["current"] == 1
    st = client.get("/api/reading/stats?months=3").json()
    assert st["by_month"][-1]["pages"] == 340 and len(st["by_month"]) == 3
    assert st["by_year"] == [{"year": today.year, "books": 1, "pages": 300}]
    assert [r["books"] for r in st["ratings"] if r["stars"] % 1 == 0] == [0, 0, 0, 1, 0] and len(st["ratings"]) == 10 and st["facts"]["longest"]["title"] == "Old one"
    feed = client.get(f"/api/activity?since={today.isoformat()}").json()
    assert {(a["verb"], a["title"]) for a in feed if a["kind"] == "book"} >= {("Read", "Now"), ("Finished", "Old one"), ("Started reading", "Now")}
    assert any(m["kind"] == "book" and m["label"] == "Now" for m in client.get("/api/journal/mentionable?q=now").json())


GOODREADS = '''Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies
101,Project Hail Mary,Andy Weir,"Weir, Andy",,"=""0593135202""","=""9780593135204""",5,4.52,Ballantine,Hardcover,496,2021,2021,2024/03/09,2024/02/01,,,read,Loved it.<br/>Rocky!,,,1,0
102,"Dune (Dune, #1)",Frank Herbert,"Herbert, Frank",,"=""""","=""""",0,4.27,Ace,Kindle Edition,,2005,1965,,2025/01/05,currently-reading,currently-reading (#1),currently-reading,,,,0,0
103,Some Slog,A. Writer,"Writer, A.",,"=""""","=""""",2,3.1,X,Audiobook,350,2019,2019,2024/07/01,2024/05/01,did-not-finish,did-not-finish (#1),did-not-finish,,,,0,0
104,Tomorrow's Book,B. Author,"Author, B.",,"=""""","=""""",0,4.0,Y,Paperback,200,2026,2026,,2026/09/01,to-read,to-read (#1),to-read,,,,0,0
'''


def test_a_goodreads_import_then_covers_from_open_library(client, ol):
    r = client.post("/api/reading/import/goodreads", content=GOODREADS.encode(), headers={"Content-Type": "text/csv"})
    assert r.status_code == 200, r.text
    assert (r.json()["added"], r.json()["updated"]) == (4, 0)
    books = {b["title"]: b for b in client.get("/api/reading/books").json()["books"]}
    hm = books["Project Hail Mary"]
    assert (hm["status"], hm["rating"], hm["finished_on"], hm["isbn"], hm["pages"], hm["review"]) == \
        ("finished", 5, "2024-03-09", "9780593135204", 496, "Loved it.\nRocky!")
    assert (books["Dune (Dune, #1)"]["status"], books["Dune (Dune, #1)"]["format"]) == ("reading", "ebook")
    assert (books["Some Slog"]["status"], books["Some Slog"]["format"]) == ("dnf", "audio")
    assert books["Tomorrow's Book"]["status"] == "want"
    # The background look-up ran after the reply: covers for the two Open Library knows.
    hm = client.get(f"/api/reading/books/{hm['book_id']}").json()
    assert hm["cover_id"] == 11200092 and hm["genres"] == ["Science fiction"]
    dune = client.get(f"/api/reading/books/{books['Dune (Dune, #1)']['book_id']}").json()
    assert (dune["cover_id"], dune["pages"]) == (11481354, 604)                # pages filled in, title search
    assert {"title": "Dune", "author": "Frank Herbert", "limit": 5} in ol      # series dropped from the title
    assert client.get("/api/reading/covers").json()["done"] == 4
    # Importing again: Goodreads' shelf and rating come back; nothing is added twice.
    client.patch(f"/api/reading/books/{hm['book_id']}", json={"rating": 3})
    r = client.post("/api/reading/import/goodreads", content=GOODREADS.encode()).json()
    assert (r["added"], r["updated"]) == (0, 4)
    assert client.get(f"/api/reading/books/{hm['book_id']}").json()["rating"] == 5
    assert client.post("/api/reading/import/goodreads", content=b"a,b\n1,2\n").status_code == 422


def test_lists_shelves_and_search(client):
    add(client, title="Alpha", author="Zed", genres=["Fantasy", "fantasy", " Horror "])
    add(client, title="Beta", author="Young", status="finished")
    r = client.get("/api/reading/books?status=finished").json()
    assert [b["title"] for b in r["books"]] == ["Beta"] and r["counts"]["want"] == 1
    assert [b["title"] for b in client.get("/api/reading/books?q=horror").json()["books"]] == ["Alpha"]
    assert client.get("/api/reading/books?q=alpha").json()["books"][0]["genres"] == ["Fantasy", "Horror"]
    assert [b["title"] for b in client.get("/api/reading/books?sort=author").json()["books"]] == ["Beta", "Alpha"]
    book_id = r["books"][0]["book_id"]
    assert client.delete(f"/api/reading/books/{book_id}").status_code == 204
    assert client.get(f"/api/reading/books/{book_id}").status_code == 404
