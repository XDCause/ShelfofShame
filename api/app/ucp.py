"""Shopify stores' official product search for apps (UCP over MCP: JSON-RPC to <store>/api/ucp/mcp),
read-only - this app asks only for the catalogue (search_catalog, get_product), never carts or checkouts.

Every call names this app with meta.ucp-agent.profile = a public JSON (ucp-agent.json in the repo, served
by jsDelivr from a git tag). Used for Good Games (goodgames.py) and Blue Sky Athletics (bluesky.py).

Each store has its own queue: one request at a time, PAUSE apart (stores rate-limit quick bursts); a 429
is waited out once (Retry-After, at most 30 s, else RETRY_WAIT), then becomes a friendly message.
"""
import json
import os
import threading
import time

import httpx

# A fixed version (git tag) of ucp-agent.json: jsDelivr serves a tag as JSON straight away and for good
# (a branch address is cached for hours after a change). A new version of the file = a new tag here.
PROFILE = "https://cdn.jsdelivr.net/gh/XDCause/ShelfofShame@ucp-agent-1/ucp-agent.json"
HEADERS = {"User-Agent": "OffTheClock/1.0 (personal hobby tracker; https://github.com/XDCause/ShelfofShame)",
           "Content-Type": "application/json", "Accept": "application/json"}
TIMEOUT = 30
PAUSE = 1.0            # between requests to one store
RETRY_WAIT = 3         # seconds to wait after a 429 without Retry-After, before the one retry


class ShopError(Exception):
    """A message for the user: the store unreachable, or it said no."""


def profile() -> str:
    """The URL of this app's UCP agent profile (UCP_PROFILE overrides it, e.g. to try a new version)."""
    return os.environ.get("UCP_PROFILE") or PROFILE


class Store:
    def __init__(self, name: str, base: str):
        self.name = name
        self.mcp = f"{base}/api/ucp/mcp"
        self.pages = f"{base}/"           # the store's own product pages (links are only kept if they start here)
        self._turn = threading.Lock()
        self._last = [0.0]

    def call(self, tool: str, catalog: dict) -> dict:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": tool, "arguments": {"meta": {"ucp-agent": {"profile": profile()}}, "catalog": catalog}}}
        for attempt in (1, 2):
            try:
                with self._turn:
                    time.sleep(max(0.0, self._last[0] + PAUSE - time.monotonic()))
                    try:
                        r = httpx.post(self.mcp, json=body, headers=HEADERS, timeout=TIMEOUT)
                    finally:
                        self._last[0] = time.monotonic()
            except httpx.HTTPError as e:
                raise ShopError(f"Couldn't reach {self.name} ({e.__class__.__name__}).") from None
            if r.status_code != 429:
                break
            if attempt == 2:
                raise ShopError(f"{self.name} asked us to slow down - try again in a minute.")
            wait = r.headers.get("Retry-After", "")
            time.sleep(min(int(wait), 30) if wait.isdigit() else RETRY_WAIT)
        try:
            reply = r.json()
        except ValueError:
            raise ShopError(f"{self.name} didn't answer (HTTP {r.status_code}).") from None
        if "error" in reply:
            err = reply["error"]
            detail = (err.get("data") or {}).get("content") if isinstance(err.get("data"), dict) else err.get("data")
            raise ShopError(f"{self.name} said no: {err.get('message')}{f' ({detail})' if detail else ''}.")
        try:
            return json.loads(reply["result"]["content"][0]["text"])
        except (KeyError, IndexError, ValueError):
            raise ShopError(f"{self.name} sent something unexpected.") from None
