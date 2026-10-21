"""Every address the web app asks for (web/src/api.js) is a real API route, with the right method - so a typo or a
renamed route fails here, not quietly in the browser. (run_tests.ps1 mounts api.js read-only; skipped without it.)"""
import re
from pathlib import Path

import pytest

from app.main import app

API_JS = Path("/web/api.js")
CALL = re.compile(r"request\(\s*([`'])(?P<path>/[^`']*)")
# how a call says its method: send('POST', ...), image('PUT', blob) or method: 'DELETE' (else it's a GET)
METHOD = re.compile(r"(?:send|image)\(\s*'(GET|POST|PUT|PATCH|DELETE)'|method:\s*'(GET|POST|PUT|PATCH|DELETE)'")


def calls() -> list[tuple[str, str, str]]:
    """(method, path with {} for each ${...}, where it is) for each request('/...') in api.js."""
    text = API_JS.read_text(encoding="utf-8")
    starts = [m for m in CALL.finditer(text)]
    out = []
    for i, m in enumerate(starts):
        path = re.sub(r"\$\{[^}`]*$", "", m.group("path"))     # `/goals${status ? `?status=...` : ''}`: a query, cut
        path = re.sub(r"\$\{[^}]*\}", "{}", path)              # ${id} -> {}
        path = path.split("?")[0]                              # the query isn't part of the route
        if path.endswith("{}") and not path.endswith("/{}"):
            path = path[:-2]                                   # `/journal${query}`
        # its method: in the call's own text (it can run onto the next lines), before the next request(
        rest = text[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)][:400]
        method = METHOD.search(rest)
        line = text[:m.start()].count("\n") + 1
        out.append(((method.group(1) or method.group(2)) if method else "GET", path, f"api.js:{line}"))
    return out


def routes() -> list[tuple[set[str], re.Pattern]]:
    """Every route from the OpenAPI description (included routers aren't flat in app.routes in this FastAPI)."""
    out = []
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api"):
            pattern = re.sub(r"\{[^}]+\}", "[^/]+", path[len("/api"):])
            out.append(({m.upper() for m in ops}, re.compile(f"^{pattern}$")))
    return out


@pytest.mark.skipif(not API_JS.exists(), reason="web/src/api.js isn't mounted (run_tests.ps1 mounts it)")
def test_every_web_call_is_a_real_route():
    known = routes()
    found = calls()
    assert len(found) > 300                                    # (the pattern still reads api.js)
    missing = []
    for method, path, line in found:
        concrete = path.replace("{}", "1")
        if not any(method in methods and rx.match(concrete) for methods, rx in known):
            missing.append(f"{method} {path}    <- {line[:110]}")
    assert not missing, "api.js asks for routes the API doesn't have:\n" + "\n".join(missing)
