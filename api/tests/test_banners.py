"""Page banners: a picture of your own for Home, the journal or a hobby, or (without one) a drawn landscape."""
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_no_banners_until_a_picture_is_added(client):
    assert client.get("/api/banners").json() == {}


def test_a_picture_for_an_area_then_moved_replaced_and_removed(client):
    r = client.put("/api/banners/area/models/photo", content=PNG, headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    banners = client.get("/api/banners").json()
    assert list(banners) == ["models"]
    first = banners["models"]
    assert first["focus_y"] == 50 and first["photo_url"].startswith(f"/api/banners/{first['banner_id']}/photo?v=")
    photo = client.get(first["photo_url"])
    assert photo.content == PNG and "immutable" in photo.headers["cache-control"]

    assert client.patch("/api/banners/area/models", json={"focus_y": 70}).json()["focus_y"] == 70
    assert client.patch("/api/banners/area/models", json={"focus_y": 101}).status_code == 422

    client.put("/api/banners/area/models/photo", content=PNG + b"1", headers={"Content-Type": "image/png"})
    again = client.get("/api/banners").json()["models"]
    assert again["banner_id"] == first["banner_id"] and again["focus_y"] == 70   # same row, the spot kept
    assert client.get(again["photo_url"]).content == PNG + b"1"

    assert client.delete("/api/banners/area/models/photo").status_code == 204
    assert client.get("/api/banners").json() == {}


def test_bad_areas_and_files_are_refused(client):
    assert client.put("/api/banners/area/Not-An-Area/photo", content=PNG,
                      headers={"Content-Type": "image/png"}).status_code == 422
    assert client.put("/api/banners/area/home/photo", content=b"<svg/>",
                      headers={"Content-Type": "image/svg+xml"}).status_code == 415
    assert client.patch("/api/banners/area/journal", json={"focus_y": 10}).status_code == 404
