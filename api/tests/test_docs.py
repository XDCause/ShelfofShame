"""The notes keep up with the code (health check, 2026-10-21: the README and CLAUDE.md had drifted weeks behind).
run_tests.ps1 mounts CLAUDE.md, README.md and docs/ read-only at /docs; skipped without them."""
import re
from pathlib import Path

import pytest

DOCS = Path("/docs")
INIT = Path("/db/init")
APP = Path(__file__).resolve().parent.parent / "app"
pytestmark = pytest.mark.skipif(not (DOCS / "CLAUDE.md").exists(), reason="the docs aren't mounted (run_tests.ps1 mounts them)")


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_claude_md_knows_the_newest_migration():
    newest = max(int(p.name[:2]) for p in INIT.glob("[0-9][0-9]_*.sql"))
    said = re.search(r"db/init \(01-(\d+)\)", read("CLAUDE.md"))
    assert said, "CLAUDE.md should say which db/init files there are: 'db/init (01-NN)'"
    assert int(said.group(1)) == newest, f"CLAUDE.md says db/init 01-{said.group(1)}; the newest is {newest:02d}"


def test_claude_md_knows_the_newest_history_entry():
    entries = re.findall(r"^(\d[a-z]*)\. \*\*", read("docs/HISTORY.md"), re.M)
    said = re.search(r"entries 3zzt - (\w+);", read("CLAUDE.md"))
    assert said, "CLAUDE.md should say which entries docs/HISTORY.md holds: 'entries 3zzt - 5x;'"
    assert said.group(1) == entries[-1], f"CLAUDE.md says HISTORY runs to {said.group(1)}; the newest entry is {entries[-1]}"
    assert (DOCS / "docs" / "HISTORY-early.md").exists()


def test_every_api_module_is_on_the_readme_map():
    readme = read("README.md")
    api = readme[readme.index("## The API"):readme.index("## Signing in")]
    mapped = set(re.findall(r"`([a-z_]+)`", api))
    modules = {p.stem for p in APP.glob("*.py") if p.stem != "__init__"}
    missing = sorted(modules - mapped)
    assert not missing, f"README.md > The API doesn't mention: {', '.join(missing)}"
    gone = sorted(m for m in mapped - modules if m not in {"api", "db"} and not m.startswith("_") and "_" in m)
    assert not gone, f"README.md > The API names modules that don't exist: {', '.join(gone)}"


def test_the_stack_map_names_everything():
    """docs/stack.html (the tech-stack map) lists every API module, every hobby and every script - so a new one fails
    here until it's on the map."""
    import json
    html = read("docs/stack.html")
    data = json.loads(re.search(r'<script type="application/json" id="stack-data">(.*?)</script>', html, re.S).group(1))
    on_map = {m for p in data["parts"] for m in p["api"]}
    modules = {p.stem for p in APP.glob("*.py") if p.stem != "__init__"}
    assert not sorted(modules - on_map), f"docs/stack.html doesn't list these API modules: {sorted(modules - on_map)}"
    assert not sorted(on_map - modules), f"docs/stack.html lists API modules that don't exist: {sorted(on_map - modules)}"
    repo = Path("/repo")
    if not repo.exists():
        return
    hobbies = {p.name for p in (repo / "web/src/modules").iterdir() if (p / "manifest.jsx").exists()}
    mapped = {p.get("hobby") for p in data["parts"] if p.get("hobby")}
    assert hobbies == mapped, f"docs/stack.html's hobbies differ: missing {sorted(hobbies - mapped)}, extra {sorted(mapped - hobbies)}"
    tools = " ".join(name for g in data["tools"] for name, _, _ in g["items"])
    scripts = sorted({p.name for p in repo.glob("*.ps1")} | {f"scripts/{p.name}" for p in (repo / "scripts").glob("*.ps1")})
    missing = [s for s in scripts if s not in tools]
    assert not missing, f"docs/stack.html's Scripts don't mention: {', '.join(missing)}"
    for p in data["parts"]:
        assert all(s in data["sites"] for s in p["sites"]), f"{p['name']} asks a site the map doesn't name"
