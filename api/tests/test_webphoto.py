"""A photo from a web address: only public addresses, only real pictures (no real network here)."""
import socket

import httpx
import pytest

from app import webphoto

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
HOSTS = {"pics.example": "93.184.216.34", "evil.example": "10.0.0.33", "localhost": "127.0.0.1", "v6.example": "::1"}


@pytest.fixture
def web(monkeypatch):
    asked = []

    def getaddrinfo(host, port, *a, **k):
        if host not in HOSTS:
            raise socket.gaierror("no such host")
        return [(None, None, None, "", (HOSTS[host], port))]

    def handler(request):
        asked.append(str(request.url))
        path = request.url.path
        if path == "/cat.png":
            return httpx.Response(200, content=PNG, headers={"content-type": "application/octet-stream"})
        if path == "/moved":
            return httpx.Response(302, headers={"location": "/cat.png"})
        if path == "/sneaky":
            return httpx.Response(302, headers={"location": "http://evil.example/secret.png"})
        if path == "/page.html":
            return httpx.Response(200, content=b"<html>hello</html>", headers={"content-type": "text/html"})
        if path == "/huge.jpg":
            return httpx.Response(200, content=JPEG + b"0" * (6 * 1024 * 1024))
        return httpx.Response(404)
    monkeypatch.setattr(webphoto.socket, "getaddrinfo", getaddrinfo)
    real = httpx.Client
    monkeypatch.setattr(webphoto.httpx, "Client", lambda **k: real(transport=httpx.MockTransport(handler), **k))
    return asked


def test_a_public_picture_comes_back(client, web):
    r = client.post("/api/photo-from-url", json={"url": "https://pics.example/cat.png"})
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"   # from its bytes
    r = client.post("/api/photo-from-url", json={"url": "https://pics.example/moved"})
    assert r.status_code == 200 and r.content == PNG


@pytest.mark.parametrize("url", ["http://localhost/x.png", "http://evil.example/x.png", "http://v6.example/x.png",
                                 "http://127.0.0.1/x.png", "http://[::1]/x.png", "http://10.0.0.33:8080/x.png",
                                 "file:///etc/passwd", "ftp://pics.example/x.png", "https://pics.example:8443/x.png",
                                 "https://nowhere.example/x.png", "https://pics.example/sneaky"])
def test_private_or_odd_addresses_are_refused(client, web, url):
    assert client.post("/api/photo-from-url", json={"url": url}).status_code == 422
    assert not any("evil.example" in a or "localhost" in a for a in web)        # never even asked


def test_only_real_pictures_and_not_too_big(client, web):
    assert "isn't a picture" in client.post("/api/photo-from-url", json={"url": "https://pics.example/page.html"}).json()["detail"]
    assert client.post("/api/photo-from-url", json={"url": "https://pics.example/huge.jpg"}).status_code == 413
    assert client.post("/api/photo-from-url", json={"url": "https://pics.example/gone.png"}).status_code == 422
