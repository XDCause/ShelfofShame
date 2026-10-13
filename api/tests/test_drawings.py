"""Drawing in the journal: sketches in notes pages, whiteboard pages, pictures, previews, search."""
from app.db import db

PNG = b"\x89PNG\r\n\x1a\nfake"


def stroke(**kw):
    return {"id": "s1", "type": "freedraw", "x": 0, "y": 0, "points": [[0, 0], [5, 9]], "pressures": [0.4, 0.7], **kw}


def words(text, y=0, **kw):
    return {"id": f"t{y}", "type": "text", "x": 10, "y": y, "text": text, "originalText": text, **kw}


def test_a_whiteboard_page_comes_with_its_board(client):
    page = client.post("/api/journal", json={"kind": "whiteboard", "title": "Paint scheme"}).json()
    assert page["kind"] == "whiteboard"
    [board] = page["drawings"]
    assert board["board"] is True and board["preview_url"] is None
    assert client.post("/api/journal", json={"kind": "sketchbook"}).status_code == 422
    assert client.get("/api/journal").json()[0]["kind"] == "whiteboard"
    assert client.delete(f"/api/journal/drawings/{board['drawing_id']}").status_code == 409   # delete the page instead


def test_saving_a_scene_keeps_strokes_drops_deleted_and_reads_the_words(client):
    page = client.post("/api/journal", json={"kind": "whiteboard", "title": "Bench"}).json()
    drawing_id = page["drawings"][0]["drawing_id"]
    url = f"/api/journal/drawings/{drawing_id}"
    r = client.put(url, json={"elements": [stroke(), words("Zero: cockpit green", y=50),
                                           words("Try XF-71", y=10), words("gone", y=0, isDeleted=True)],
                              "app_state": {"viewBackgroundColor": "#fffbe6", "gridModeEnabled": True,
                                            "zoom": {"value": 2}, "selectedElementIds": {"s1": True}}})
    assert r.status_code == 200, r.text
    got = client.get(url).json()
    assert [e["id"] for e in got["scene"]["elements"]] == ["s1", "t50", "t10"]
    assert got["scene"]["appState"] == {"viewBackgroundColor": "#fffbe6", "gridModeEnabled": True}  # not zoom etc.
    assert got["text"] == "Try XF-71\nZero: cockpit green"                         # top to bottom
    # ...and the page can be found by what's written on the board
    assert [p["title"] for p in client.get("/api/journal?q=cockpit").json()] == ["Bench"]


def test_pictures_are_sent_once_and_merged(client):
    page = client.post("/api/journal", json={"kind": "whiteboard"}).json()
    url = f"/api/journal/drawings/{page['drawings'][0]['drawing_id']}/files"
    one = {"mimeType": "image/jpeg", "dataURL": "data:image/jpeg;base64,/9j/AAA="}
    assert client.put(url, json={"f1": one}).status_code == 200
    assert client.put(url, json={"f2": {**one, "mimeType": "image/png"}}).status_code == 200
    files = client.get(url.removesuffix("/files")).json()["files"]
    assert sorted(files) == ["f1", "f2"]
    assert client.put(url, json={"f3": {"mimeType": "text/html", "dataURL": "data:text/html,hi"}}).status_code == 422
    assert client.put(url, json={"f3": {"mimeType": "image/png", "dataURL": "https://x"}}).status_code == 422


def test_preview_is_the_page_picture_and_changes_address_when_redrawn(client):
    page = client.post("/api/journal", json={"kind": "whiteboard", "title": "Board"}).json()
    drawing_id = page["drawings"][0]["drawing_id"]
    url = f"/api/journal/drawings/{drawing_id}/preview"
    assert client.get(url).status_code == 404
    first = client.put(url, content=PNG, headers={"Content-Type": "image/png"}).json()["preview_url"]
    assert client.get(url).content == PNG
    [listed] = client.get("/api/journal").json()
    assert listed["cover_url"] == first                                            # the list's picture
    second = client.put(url, content=PNG + b"2", headers={"Content-Type": "image/png"}).json()["preview_url"]
    assert second != first
    assert client.put(url, content=b"<svg/>", headers={"Content-Type": "image/svg+xml"}).status_code == 415


def test_sketches_in_a_notes_page_and_removing_one(client):
    page = client.post("/api/journal", json={"title": "Notes"}).json()
    sketch = client.post(f"/api/journal/{page['page_id']}/drawings")
    assert sketch.status_code == 201
    sketch = sketch.json()
    assert sketch["board"] is False
    block = {"type": "drawing", "props": {"drawingId": str(sketch["drawing_id"])}, "children": []}
    client.patch(f"/api/journal/{page['page_id']}", json={"content": [block]})
    assert [d["drawing_id"] for d in client.get(f"/api/journal/{page['page_id']}").json()["drawings"]] == \
        [sketch["drawing_id"]]
    # The block is deleted: the sketch stays a while (undo), then goes at the next save.
    client.patch(f"/api/journal/{page['page_id']}", json={"content": []})
    assert len(client.get(f"/api/journal/{page['page_id']}").json()["drawings"]) == 1
    with db() as conn:   # an hour later (past the trigger that stamps updated_at)
        conn.execute("SET LOCAL session_replication_role = replica")
        conn.execute("UPDATE journal_drawings SET updated_at = now() - interval '1 hour'")
    client.patch(f"/api/journal/{page['page_id']}", json={"content": []})
    assert client.get(f"/api/journal/{page['page_id']}").json()["drawings"] == []
    assert client.post("/api/journal/9999/drawings").status_code == 404


def test_deleting_a_page_deletes_its_drawings(client):
    page = client.post("/api/journal", json={"kind": "whiteboard"}).json()
    drawing_id = page["drawings"][0]["drawing_id"]
    assert client.delete(f"/api/journal/{page['page_id']}").status_code == 204
    assert client.get(f"/api/journal/drawings/{drawing_id}").status_code == 404


def test_a_whiteboard_is_drawn_not_written_in_activity(client):
    client.post("/api/journal", json={"kind": "whiteboard", "title": "Layout"})
    client.post("/api/journal", json={"title": "Diary"})
    feed = {f["title"]: f["verb"] for f in client.get("/api/activity").json()}
    assert feed == {"Layout": "Drew", "Diary": "Wrote"}
