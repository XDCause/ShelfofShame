"""Series: moved out of Goodreads-style titles, every book in a series (Wikidata + Open Library,
both faked - made-up answers in their layouts), merged with your books; and the On my shelf shelf."""
import pytest

from app import bookseries, openlibrary, reading


def wd_row(series_qid, series, book_qid, title, ordinal=None, year=None, author="Pierce Brown"):
    row = {"series": {"value": f"http://www.wikidata.org/entity/{series_qid}"}, "seriesLabel": {"value": series},
           "book": {"value": f"http://www.wikidata.org/entity/{book_qid}"}, "bookLabel": {"value": title},
           "authorLabel": {"value": author}}
    if ordinal is not None:
        row["ord"] = {"value": str(ordinal)}
    if year:
        row["date"] = {"value": f"{year}-01-01T00:00:00Z"}
    return row


SAGA = [
    wd_row("Q1", "Red Rising Saga", "Q11", "Red Rising", 1, 2014),
    wd_row("Q1", "Red Rising Saga", "Q12", "Golden Son", 2, 2015),
    wd_row("Q1", "Red Rising Saga", "Q14", "Iron Gold", 4, 2018),
    wd_row("Q1", "Red Rising Saga", "Q15", "Dark Age", 5, 2019),
    wd_row("Q1", "Red Rising Saga", "Q13", "Morning Star", 3, 2016),
    wd_row("Q1", "Red Rising Saga", "Q17", "Red God", 7),                    # not out yet
    wd_row("Q2", "Red Rising Trilogy", "Q11", "Red Rising", 1, 2014),         # the trilogy inside it: fewer books
    wd_row("Q1", "Red Rising Saga", "Q99", "Somebody Else's Book", 6, 2020, author="Another Writer"),
]


def ol_doc(work, title, cover=5, author="Pierce Brown", year=2015):
    return {"key": f"/works/{work}", "title": title, "author_name": [author], "first_publish_year": year,
            "number_of_pages_median": 400, "cover_i": cover, "ratings_count": 10}


@pytest.fixture
def sources(monkeypatch):
    asked = {"wikidata": 0, "ol": []}

    def wikidata(query):
        asked["wikidata"] += 1
        return SAGA if '"Red Rising Saga"' in query else []

    def ol(params):
        asked["ol"].append(params["q"])
        if params["q"].startswith('author:"Pierce Brown"'):
            return [ol_doc("OL1W", "Red Rising", 11), ol_doc("OL4W", "Iron Gold", 44), ol_doc("OL5W", "Dark Age", 55, year=2015)]
        if params["q"].startswith('series:"Bloodsworn"'):
            return [ol_doc("OL31W", "The Fury of the Gods", 3, "John Gwynne", 2024),
                    ol_doc("OL30W", "The Shadow of the Gods", 1, "John Gwynne", 2021),
                    ol_doc("OL32W", "Bloodsworn Box Set", 9, "John Gwynne", 2025)]
        return []
    monkeypatch.setattr(bookseries, "_wikidata", wikidata)
    monkeypatch.setattr(openlibrary, "_get", ol)
    return asked


def add(client, **book):
    r = client.post("/api/reading/books", json=book)
    assert r.status_code == 201, r.text
    return r.json()


def test_series_comes_out_of_the_title():
    assert reading.split_series("Golden Son (Red Rising Saga, #2)") == ("Golden Son", "Red Rising Saga", 2.0)
    assert reading.split_series("The Way of Kings (The Stormlight Archive, #1.5)") == ("The Way of Kings", "The Stormlight Archive", 1.5)
    assert reading.split_series("Dune") == ("Dune", None, None)
    assert reading.split_series("(Not a series, #1)") == ("(Not a series, #1)", None, None)


def test_a_series_in_order_with_your_books(client, sources):
    first = add(client, title="Red Rising (Red Rising Saga, #1)", author="Pierce Brown", status="finished", rating=5)
    assert (first["title"], first["series"], float(first["series_number"])) == ("Red Rising", "Red Rising Saga", 1.0)
    gold = add(client, title="Iron Gold", author="Pierce Brown", status="owned")          # no series yet
    r = client.get(f"/api/reading/books/{first['book_id']}/series").json()
    assert (r["series"], r["source"], r["error"]) == ("Red Rising Saga", "wikidata", None)
    rows = [(b["title"], b["number"], b["book_id"] is not None) for b in r["books"]]
    assert rows == [("Red Rising", 1, True), ("Golden Son", 2, False), ("Morning Star", 3, False),
                    ("Iron Gold", 4, True), ("Dark Age", 5, False), ("Red God", 7, False)]   # not the other author's
    by = {b["title"]: b for b in r["books"]}
    assert by["Red Rising"]["this"] and by["Red Rising"]["rating"] == 5 and by["Red Rising"]["status"] == "finished"
    assert by["Dark Age"]["year"] == 2019 and by["Dark Age"]["cover_url"].endswith("/55-M.jpg")   # Wikidata's year, OL's cover
    assert by["Red God"]["upcoming"] and not by["Dark Age"]["upcoming"] and by["Golden Son"]["cover_url"] is None
    # Iron Gold was found in the series: it learns its series and number.
    gold = client.get(f"/api/reading/books/{gold['book_id']}").json()
    assert (gold["series"], float(gold["series_number"])) == ("Red Rising Saga", 4.0)
    # Asked again: from the cache, no more requests.
    calls = sources["wikidata"], len(sources["ol"])
    assert client.get(f"/api/reading/books/{gold['book_id']}/series").json()["books"][3]["this"]
    assert (sources["wikidata"], len(sources["ol"])) == calls


def test_open_library_when_wikidata_has_nothing(client, sources):
    book = add(client, title="The Shadow of the Gods (Bloodsworn, #1)", author="John Gwynne")
    r = client.get(f"/api/reading/books/{book['book_id']}/series").json()
    assert r["source"] == "openlibrary"
    assert [(b["title"], b["book_id"] is not None) for b in r["books"]] == \
        [("The Shadow of the Gods", True), ("The Fury of the Gods", False)]   # yours numbered first; no box set
    assert any(q.startswith('series:"Bloodsworn" author:"John Gwynne"') for q in sources["ol"])


def test_no_series(client, sources):
    book = add(client, title="Project Hail Mary", author="Andy Weir")
    assert client.get(f"/api/reading/books/{book['book_id']}/series").json() == {"series": None, "books": []}
    assert sources["wikidata"] == 0


def test_on_my_shelf(client):
    owned = add(client, title="Owned One", status="owned")
    add(client, title="Wanted One", status="want")
    s = client.get("/api/reading/summary").json()
    assert s["counts"]["owned"] == 1 and [b["title"] for b in s["next_up"]] == ["Owned One", "Wanted One"]
    assert [b["title"] for b in client.get("/api/reading/books?status=owned").json()["books"]] == ["Owned One"]
    r = client.post(f"/api/reading/books/{owned['book_id']}/progress", json={"page": 10}).json()   # starting it
    assert r["status"] == "reading"
    assert client.post("/api/reading/books", json={"title": "X", "status": "shelf"}).status_code == 422


def test_goodreads_owned_shelf_and_series(client):
    csv = ("Book Id,Title,Author,ISBN,ISBN13,My Rating,Number of Pages,Year Published,Date Read,Date Added,Exclusive Shelf\n"
           '1,"Golden Son (Red Rising Saga, #2)",Pierce Brown,,,0,442,2015,,2024/01/01,owned-tbr\n')
    r = client.post("/api/reading/import/goodreads", content=csv.encode(), headers={"Content-Type": "text/csv"})
    assert r.json()["added"] == 1
    [b] = client.get("/api/reading/books").json()["books"]
    assert (b["title"], b["series"], float(b["series_number"]), b["status"]) == ("Golden Son", "Red Rising Saga", 2.0, "owned")
