"""The journal: pages, search, tags, @mentions (links both ways) and photos."""
from datetime import date

from app import journal


def mention(kind, ref, label):
    return {"type": "mention", "props": {"kind": kind, "ref": str(ref), "label": label}}


def paragraph(*content, children=()):
    return {"type": "paragraph", "props": {}, "content": list(content), "children": list(children)}


def text(words):
    return {"type": "text", "text": words, "styles": {}}


def make_model(client, name="M4A3E8 Sherman"):
    return client.post("/api/models", json={"name": name}).json()


# ---------------------------------------------------------------- reading the blocks
def test_plain_text_takes_words_from_every_kind_of_block():
    blocks = [
        {"type": "heading", "props": {"level": 1}, "content": [text("Hull")], "children": []},
        paragraph(text("Primed with "), mention("supply", 4, "XF-1"), text(" today"),
                  children=[paragraph(text("nested note"))]),
        {"type": "paragraph", "content": [{"type": "link", "href": "https://x", "content": [text("a link")]}]},
        {"type": "table", "content": {"type": "tableContent", "rows": [
            {"cells": [[text("cell one")], {"type": "tableCell", "content": [text("cell two")]}]}]}},
        {"type": "image", "props": {"url": "/api/journal/images/1"}, "children": []},
    ]
    assert journal.plain_text(blocks) == "Hull\nPrimed with @XF-1 today\nnested note\na link\ncell one cell two"


def test_mentions_are_found_anywhere_and_bad_ones_ignored():
    blocks = [paragraph(mention("model", 3, "Sherman"), children=[paragraph(mention("supply", 7, "XF-62"))]),
              paragraph(mention("model", 3, "Sherman again"), mention("dragon", 1, "?"), mention("page", "x", "?"))]
    assert journal.mentions(blocks) == {("model", 3), ("supply", 7)}


# ---------------------------------------------------------------- pages
def test_a_new_page_is_dated_today_and_untitled(client):
    page = client.post("/api/journal", json={}).json()
    assert page["title"] == "" and page["entry_date"] == date.today().isoformat()
    assert page["content"] == [] and page["tags"] == [] and page["links"] == []


def test_saving_a_page_keeps_its_blocks_text_and_mentions(client):
    sherman = make_model(client)
    page = client.post("/api/journal", json={"title": "Sunday at the bench"}).json()
    blocks = [paragraph(text("Started the "), mention("model", sherman["model_id"], "Sherman"), text(" hull"))]
    saved = client.patch(f"/api/journal/{page['page_id']}", json={"content": blocks}).json()
    assert saved["content"] == blocks
    assert saved["text"] == "Started the @Sherman hull"
    assert saved["links"] == [{"kind": "model", "id": sherman["model_id"], "name": "M4A3E8 Sherman"}]

    # The model lists the page, and the link goes when the mention does.
    about = client.get(f"/api/journal?mention=model:{sherman['model_id']}").json()
    assert [p["title"] for p in about] == ["Sunday at the bench"]
    client.patch(f"/api/journal/{page['page_id']}", json={"content": [paragraph(text("no mention now"))]})
    assert client.get(f"/api/journal?mention=model:{sherman['model_id']}").json() == []


def test_pages_mentioning_a_page_and_not_itself(client):
    a = client.post("/api/journal", json={"title": "Paint plan"}).json()
    b = client.post("/api/journal", json={"title": "Build day", "content": [paragraph(mention("page", a["page_id"], "Paint plan"))]}).json()
    client.patch(f"/api/journal/{a['page_id']}", json={"content": [paragraph(mention("page", a["page_id"], "me"))]})
    a = client.get(f"/api/journal/{a['page_id']}").json()
    assert a["links"] == []                                       # mentioning itself isn't kept
    assert [p["title"] for p in a["mentioned_in"]] == ["Build day"]
    assert client.get(f"/api/journal/{b['page_id']}").json()["links"][0]["name"] == "Paint plan"


def test_list_newest_first_pinned_on_top_with_snippets(client):
    client.post("/api/journal", json={"title": "Old", "entry_date": "2026-01-01"})
    client.post("/api/journal", json={"title": "New", "entry_date": "2026-10-01",
                                      "content": [paragraph(text("A long day of sanding"))]})
    client.post("/api/journal", json={"title": "Pinned ideas", "entry_date": "2025-05-05", "pinned": True})
    pages = client.get("/api/journal").json()
    assert [p["title"] for p in pages] == ["Pinned ideas", "New", "Old"]
    assert pages[1]["snippet"] == "A long day of sanding"
    assert "content" not in pages[0]                             # the list stays light


def test_search_every_word_in_title_or_text(client):
    client.post("/api/journal", json={"title": "Sherman weathering", "content": [paragraph(text("pigments and oils"))]})
    client.post("/api/journal", json={"title": "Zero cockpit", "content": [paragraph(text("oils on the seat"))]})
    assert {p["title"] for p in client.get("/api/journal?q=oils").json()} == {"Sherman weathering", "Zero cockpit"}
    assert [p["title"] for p in client.get("/api/journal?q=sherman OILS").json()] == ["Sherman weathering"]
    assert client.get("/api/journal?q=volleyball").json() == []


def test_tags_are_tidied_listed_filtered_and_forgotten(client):
    page = client.post("/api/journal", json={"title": "Club night", "tags": [" painting", "Ideas", "painting", ""]}).json()
    assert page["tags"] == ["Ideas", "painting"]
    client.post("/api/journal", json={"title": "Other", "tags": ["painting"]})
    assert client.get("/api/journal/tags").json() == [{"name": "Ideas", "pages": 1}, {"name": "painting", "pages": 2}]
    assert [p["title"] for p in client.get("/api/journal?tag=Ideas").json()] == ["Club night"]
    client.patch(f"/api/journal/{page['page_id']}", json={"tags": ["painting"]})
    assert [t["name"] for t in client.get("/api/journal/tags").json()] == ["painting"]   # unused tag gone


def test_editing_title_date_icon_and_pin(client):
    page = client.post("/api/journal", json={}).json()
    url = f"/api/journal/{page['page_id']}"
    saved = client.patch(url, json={"title": "Dive trip plans", "entry_date": "2026-11-02", "icon": "🤿", "pinned": True}).json()
    assert (saved["title"], saved["entry_date"], saved["icon"], saved["pinned"]) == ("Dive trip plans", "2026-11-02", "🤿", True)
    assert client.patch(url, json={"entry_date": None}).status_code == 422
    assert client.patch("/api/journal/999", json={"title": "x"}).status_code == 404


def test_deleting_a_page_removes_links_to_it(client):
    a = client.post("/api/journal", json={"title": "Doomed"}).json()
    b = client.post("/api/journal", json={"title": "Keeper", "content": [paragraph(mention("page", a["page_id"], "Doomed"))]}).json()
    assert client.delete(f"/api/journal/{a['page_id']}").status_code == 204
    assert client.get(f"/api/journal/{a['page_id']}").status_code == 404
    assert client.get(f"/api/journal/{b['page_id']}").json()["links"] == []


def test_mentionable_finds_models_supplies_and_pages(client, make_supply):
    make_model(client, "M4A3E8 Sherman")
    make_supply(product_code="T81762", name="Acrylic XF62 Olive Drab")
    client.post("/api/journal", json={"title": "Sherman paint notes"})
    found = client.get("/api/journal/mentionable?q=sherman").json()
    assert [(f["kind"], f["label"]) for f in found] == [("model", "M4A3E8 Sherman"), ("page", "Sherman paint notes")]
    by_code = client.get("/api/journal/mentionable?q=T81762").json()
    assert [(f["kind"], f["what"]) for f in by_code] == [("supply", "Supply")]


def test_photos_in_pages(client):
    page = client.post("/api/journal", json={}).json()
    r = client.post(f"/api/journal/images?page_id={page['page_id']}", content=b"\x89PNGfake",
                    headers={"content-type": "image/png"})
    assert r.status_code == 201
    image = client.get(r.json()["url"])
    assert image.status_code == 200 and image.content == b"\x89PNGfake" and image.headers["content-type"] == "image/png"
    assert client.post("/api/journal/images", content=b"x", headers={"content-type": "text/plain"}).status_code == 415
