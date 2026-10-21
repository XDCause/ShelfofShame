"""Settings > System and Home's "needs a look" (api/app/system.py): each check's state from backups/status.json,
backups/updates.json, the backup files themselves and the database."""
import json
from datetime import datetime, timedelta

import pytest

from app import settings
from app.db import db


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")              # (the Google Drive copy is prod's; tests run in dev's container)
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    return tmp_path


def stamp(when: datetime) -> str:
    return when.strftime("%Y%m%d_%H%M%S")


def by_key(client):
    return {c["key"]: c for c in client.get("/api/system").json()["checks"]}


def test_no_backups_yet_is_red(client, folder):
    out = client.get("/api/system").json()
    assert out["worst"] == "bad" and by_key(client)["backup"]["state"] == "bad"
    assert any(c["key"] == "backup" for c in out["attention"])


def test_a_fresh_checked_backup_and_restore_test_are_green(client, folder):
    now = datetime.now()
    name = f"hobby_inventory_{stamp(now - timedelta(hours=3))}.dump"
    (folder / name).write_bytes(b"PGDMP")
    (folder / "status.json").write_text(json.dumps({
        "backup": {"at": (now - timedelta(hours=3)).isoformat(timespec="seconds"), "ok": True, "name": name},
        "restore_test": {"at": (now - timedelta(days=2)).isoformat(timespec="seconds"), "ok": True, "tables": 105, "rows": 900},
        "offsite": {"at": (now - timedelta(hours=3)).isoformat(timespec="seconds"), "ok": True, "files": 5, "mb": 55, "budget_mb": 2048,
                    "videos": 4, "videos_mb": 5102},
    }))
    (folder / "updates.json").write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "outdated": 2, "audit_problems": 0}))
    with db() as conn:
        conn.execute("INSERT INTO site_checks (site, ok, checked_at) VALUES ('tamiya', true, now())")
    c = by_key(client)
    assert c["backup"]["state"] == "ok" and "read back and checked" in c["backup"]["detail"]
    assert c["restore"]["state"] == "ok" and "105 tables" in c["restore"]["detail"]
    assert c["offsite"]["state"] == "ok" and "55 MB" in c["offsite"]["detail"]
    assert "videos: 4 (5.0 GB)" in c["offsite"]["detail"]
    assert "copy" not in c                                                     # (no network drive: no line for it)
    assert c["updates"]["state"] == "ok" and c["sites"]["state"] == "ok" and c["disk"]["state"] in ("ok", "warn", "bad")
    assert c["steam"]["state"] == "off"


def test_old_failed_and_stale_things_ask_for_a_look(client, folder):
    now = datetime.now()
    (folder / f"hobby_inventory_{stamp(now - timedelta(days=4))}.dump").write_bytes(b"PGDMP")
    (folder / "status.json").write_text(json.dumps({
        "restore_test": {"at": (now - timedelta(days=1)).isoformat(timespec="seconds"), "ok": False, "message": "rows missing: supplies"},
        "offsite": {"at": now.isoformat(timespec="seconds"), "ok": False, "message": "Google Drive isn't there"},
    }))
    (folder / "updates.json").write_text(json.dumps({"at": (now - timedelta(days=50)).isoformat(timespec="seconds"), "outdated": 9,
                                                      "audit_problems": 1}))
    c = by_key(client)
    assert c["backup"]["state"] == "warn" and "4 days ago" in c["backup"]["detail"]
    assert c["restore"]["state"] == "bad" and "rows missing" in c["restore"]["detail"]
    assert c["offsite"]["state"] == "bad" and c["offsite"]["fix"]
    assert c["updates"]["state"] == "warn" and "1 security problem" in c["updates"]["detail"]
    assert c["sites"]["state"] == "warn"                                       # never run
    assert client.get("/api/system").json()["worst"] == "bad"


def test_a_failed_backup_after_the_last_good_one_is_red(client, folder):
    now = datetime.now()
    (folder / f"hobby_inventory_{stamp(now - timedelta(hours=26))}.dump").write_bytes(b"PGDMP")
    (folder / "status.json").write_text(json.dumps({"backup": {"at": now.isoformat(timespec="seconds"), "ok": False,
                                                               "message": "db is not running/healthy"}}))
    assert by_key(client)["backup"]["state"] == "bad"


def test_junk_status_files_are_ignored(client, folder):
    (folder / "status.json").write_text("{not json")
    (folder / "updates.json").write_bytes(b"\xff\xfe")
    assert client.get("/api/system").status_code == 200


def test_the_drive_copy_is_prod_only(client, folder, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    assert by_key(client)["offsite"] == {**by_key(client)["offsite"], "state": "off", "detail": "Prod only"}


def test_a_network_copy_failing_night_after_night_is_red_with_since_when(client, folder):
    now = datetime.now()
    (folder / f"hobby_inventory_{stamp(now - timedelta(hours=6))}.dump").write_bytes(b"PGDMP")
    (folder / "status.json").write_text(json.dumps({"copy": {
        "at": (now - timedelta(hours=6)).isoformat(timespec="seconds"), "ok": False, "to": r"\10.0.0.9\Disk\Off the Clock backups",
        "message": "The network name cannot be found.\r\n", "failing_since": (now - timedelta(days=3, hours=6)).isoformat(timespec="seconds"),
        "failures": 4}}))
    c = by_key(client)["copy"]
    assert c["state"] == "bad" and "4 runs in a row" in c["detail"] and c["detail"].startswith("Failing since")
    assert "\\10.0.0.9 in File Explorer" in c["fix"]
    assert client.get("/api/system").json()["worst"] == "bad"


def test_a_first_network_copy_failure_is_amber_and_a_quiet_one_too(client, folder):
    now = datetime.now()
    first = {"at": now.isoformat(timespec="seconds"), "ok": False, "to": r"\nas\share", "message": "busy", "failures": 1,
             "failing_since": now.isoformat(timespec="seconds")}
    (folder / "status.json").write_text(json.dumps({"copy": first}))
    assert by_key(client)["copy"]["state"] == "warn"
    quiet = {"at": (now - timedelta(days=5)).isoformat(timespec="seconds"), "ok": True, "to": r"\nas\share"}
    (folder / "status.json").write_text(json.dumps({"copy": quiet}))
    c = by_key(client)["copy"]
    assert c["state"] == "warn" and "Task Scheduler" in c["fix"]
