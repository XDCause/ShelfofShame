"""How the app itself is doing (health check, 2026-10-21): Settings > System lists every check; Home shows the ones
that need a look (amber or red). Nothing here changes anything.

    backup        the newest backup (backup.ps1 at 2 am, or Back up now): amber after 2 days, red after 7 or if it failed
    restore test  the weekly real restore into a throwaway database (backup.ps1): amber if over 9 days old, red if failed
    off-site      the encrypted copy in Google Drive (prod only, once setup-offsite.ps1 has run)
    network copy  the copy on the network drive (backup.ps1 -CopyTo)
    steam         the daily Steam sync (when a key and a profile are set)
    sites         the weekly check of the websites the app reads
    disk          space left on the PC (the backups folder's drive)
    updates       the monthly update check (check-updates.ps1): amber if over 40 days, or if the audits found problems

backup.ps1 and check-updates.ps1 write backups/status.json and backups/updates.json (the folder both the scripts and
this container see); the rest comes from the database.
"""
import json
import os
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter

from .db import db
from . import settings
from .settings import BACKUP_NAME

router = APIRouter(prefix="/api", tags=["settings"])

ORDER = {"ok": 0, "off": 0, "warn": 1, "bad": 2}


def _read(name: str) -> dict:
    try:
        return json.loads((settings.BACKUP_DIR / name).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _at(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None) if value else None
    except ValueError:
        return None


def _ago(when: datetime | None, now: datetime) -> str:
    if not when:
        return "never"
    hours = (now - when).total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 36:
        return f"{round(hours)} hour{'' if round(hours) == 1 else 's'} ago"
    return f"{round(hours / 24)} days ago"


def check(key: str, label: str, state: str, detail: str, at: datetime | None = None, fix: str | None = None) -> dict:
    return {"key": key, "label": label, "state": state, "detail": detail, "at": at, "fix": fix}


def backup_checks(now: datetime, status: dict) -> list[dict]:
    out = []
    files = sorted((p for p in settings.BACKUP_DIR.glob("hobby_inventory_*.dump") if BACKUP_NAME.match(p.name)), reverse=True) \
        if settings.BACKUP_DIR.is_dir() else []
    newest = datetime.strptime(files[0].name[16:31], "%Y%m%d_%H%M%S") if files else None
    last = status.get("backup") or {}
    failed = last.get("ok") is False and (not newest or (_at(last.get("at")) or now) >= newest)
    if failed:
        out.append(check("backup", "Backup", "bad", f"The last backup failed: {last.get('message')}", _at(last.get("at")),
                         "Settings > Backups > Back up now, then look at backups\\backup.log"))
    elif not newest:
        out.append(check("backup", "Backup", "bad", "No backups yet", None, "Settings > Backups > Back up now"))
    else:
        age = now - newest
        state = "ok" if age <= timedelta(days=2) else "warn" if age <= timedelta(days=7) else "bad"
        out.append(check("backup", "Backup", state, f"Last backup {_ago(newest, now)}" +
                         (" (read back and checked)" if last.get("ok") and last.get("name") == files[0].name else ""), newest,
                         None if state == "ok" else "Is the PC on at 2 am? Task Scheduler > \"Shelf of Shame backup\""))
    test = status.get("restore_test") or {}
    when = _at(test.get("at"))
    if not test:
        out.append(check("restore", "Test restore", "warn", "Not done yet - the next nightly backup does one", None))
    elif test.get("ok") is False:
        out.append(check("restore", "Test restore", "bad", f"The test restore failed: {test.get('message')}", when,
                         "Run .\\backup.ps1 -TestRestore and look at backups\\backup.log"))
    else:
        stale = now - when > timedelta(days=9)
        out.append(check("restore", "Test restore", "warn" if stale else "ok",
                         f"Restored {_ago(when, now)}: {test.get('tables')} tables, {test.get('rows')} rows, all there", when,
                         "Run .\\backup.ps1 -TestRestore" if stale else None))
    off = status.get("offsite") or {}
    when = _at(off.get("at"))
    if os.environ.get("APP_ENV", "prod") != "prod":
        out.append(check("offsite", "Google Drive copy", "off", "Prod only", None))
    elif not off:
        out.append(check("offsite", "Google Drive copy", "off", "Not set up", None, "Run .\\setup-offsite.ps1 in the prod folder"))
    elif off.get("ok") is False:
        out.append(check("offsite", "Google Drive copy", "bad", f"Failed: {off.get('message')}", when,
                         "Is Google Drive for desktop running and signed in?"))
    else:
        stale = now - when > timedelta(days=3)
        out.append(check("offsite", "Google Drive copy", "warn" if stale else "ok",
                         f"Encrypted copy {_ago(when, now)} - {off.get('files')} kept, {off.get('mb')} MB of the "
                         f"{off.get('budget_mb')} MB allowed" + (f"; videos: {off['videos']} ({off.get('videos_mb', 0) / 1024:.1f} GB)"
                                                                if off.get("videos") is not None else ""), when))
    if off and os.environ.get("APP_ENV", "prod") == "prod":
        out += drive_checks(now, status)
    out.append(copy_check(now, status.get("copy") or {}))
    return [c for c in out if c]


def drive_checks(now: datetime, status: dict) -> list[dict]:
    """Has Google finished uploading (backup.ps1 + drivecheck.py), and the monthly restore from a Drive copy."""
    out = []
    sync = status.get("drive_sync") or {}
    when = _at(sync.get("at"))
    if not sync or sync.get("ok") is None:
        out.append(check("drive_sync", "Drive upload", "off", sync.get("message") or "Not checked yet - the next nightly backup does", when))
    elif sync.get("ok"):
        out.append(check("drive_sync", "Drive upload", "ok", f"All {sync.get('checked')} files are up on Google Drive (checked {_ago(when, now)})", when))
    else:
        runs = int(sync.get("failures") or 1)
        out.append(check("drive_sync", "Drive upload", "bad" if runs >= 2 else "warn",
                         f"{sync.get('message')}" + (f" ({runs} nights running)" if runs > 1 else "") +
                         (f": {sync['pending']}" if sync.get("pending") else ""), when,
                         "Is Google Drive for desktop running and signed in? Its icon in the taskbar shows what's left to upload"))
    test = status.get("drive_restore") or {}
    when = _at(test.get("at"))
    if not test:
        out.append(check("drive_restore", "Restore from Drive", "warn", "Not done yet - the next nightly backup does one", None))
    elif test.get("ok") is False:
        out.append(check("drive_restore", "Restore from Drive", "bad", f"Failed: {test.get('message')}", when,
                         "Run .\\backup.ps1 -TestRestore in the prod folder and look at backups\\backup.log"))
    else:
        stale = now - when > timedelta(days=35)
        out.append(check("drive_restore", "Restore from Drive", "warn" if stale else "ok",
                         f"A copy from Google Drive restored {_ago(when, now)}: {test.get('tables')} tables, {test.get('rows')} rows, all there",
                         when, "Run .\\backup.ps1 -TestRestore in the prod folder" if stale else None))
    return out


def copy_check(now: datetime, copy: dict) -> dict | None:
    """The copy on the network drive: red once it has failed for more than a day (backup.ps1 keeps failing_since and
    the runs in a row), amber on a first failure or when no copy has been tried for 3 days. (2026-10-22: it failed
    four nights running - the drive on the modem sleeps - before anyone noticed.)"""
    if not copy:
        return None
    when = _at(copy.get("at"))
    if copy.get("ok") is False:
        since = _at(copy.get("failing_since")) or when
        runs = int(copy.get("failures") or 1)
        long = since and now - since > timedelta(days=1)
        detail = (f"Failing since {since:%a %d %b} ({runs} runs in a row): {copy.get('message', '').strip()}" if runs > 1 or long
                  else f"Failed {_ago(when, now)}: {copy.get('message', '').strip()}")
        server = "\\\\" + (copy.get("to") or "").lstrip("\\").split("\\")[0]      # (\\<host>, from its own path)
        return check("copy", "Network drive copy", "bad" if long or runs >= 2 else "warn", detail, when,
                     f"Is the network drive plugged in and on? Open {server} in File Explorer to wake it")
    stale = not when or now - when > timedelta(days=3)
    return check("copy", "Network drive copy", "warn" if stale else "ok", f"Copied {_ago(when, now)} (checked: identical)", when,
                 "Is the 2 am backup running? Task Scheduler > \"Shelf of Shame backup\"" if stale else None)


def other_checks(now: datetime) -> list[dict]:
    out = []
    with db() as conn:
        steam = conn.execute("SELECT steam_id, last_sync_at, last_error FROM vg_sync WHERE id = 1").fetchone()
        sites = conn.execute("SELECT max(checked_at) AS last, count(*) FILTER (WHERE NOT ok) AS failing FROM site_checks").fetchone()
    if os.environ.get("STEAM_API_KEY") and steam and steam["steam_id"]:
        when = steam["last_sync_at"].astimezone().replace(tzinfo=None) if steam["last_sync_at"] else None
        if steam["last_error"]:
            out.append(check("steam", "Steam sync", "warn", f"The last sync failed: {steam['last_error']}", when, "Video games > Sync now"))
        else:
            stale = not when or now - when > timedelta(days=3)
            out.append(check("steam", "Steam sync", "warn" if stale else "ok", f"Synced {_ago(when, now)}", when,
                             "Video games > Sync now" if stale else None))
    else:
        out.append(check("steam", "Steam sync", "off", "No Steam key or profile set", None))
    when = sites["last"].astimezone().replace(tzinfo=None) if sites["last"] else None
    if not when:
        out.append(check("sites", "Website check", "warn", "Not run yet", None, "Settings > Lookup sites > Check now"))
    else:
        state = "warn" if sites["failing"] or now - when > timedelta(days=9) else "ok"
        out.append(check("sites", "Website check", state,
                         f"Checked {_ago(when, now)}" + (f" - {sites['failing']} site{'s' if sites['failing'] != 1 else ''} failing"
                                                           if sites["failing"] else ", every site fine"), when,
                         "Settings > Lookup sites" if state != "ok" else None))
    try:
        free = shutil.disk_usage(settings.BACKUP_DIR).free / 1e9
        state = "ok" if free >= 20 else "warn" if free >= 5 else "bad"
        out.append(check("disk", "Disk space", state, f"{free:.0f} GB free", None, None if state == "ok" else "Free up space on the PC"))
    except OSError:
        pass
    up = _read("updates.json")
    when = _at(up.get("at"))
    if not up:
        out.append(check("updates", "Updates", "warn", "Never checked", None, "Run .\\check-updates.ps1 in the dev folder"))
    else:
        problems = int(up.get("audit_problems") or 0)
        state = "warn" if problems or now - when > timedelta(days=40) else "ok"
        out.append(check("updates", "Updates", state,
                         f"Checked {_ago(when, now)}: {up.get('outdated', 0)} newer version{'s' if up.get('outdated') != 1 else ''} "
                         f"available" + (f", {problems} security problem{'s' if problems != 1 else ''}" if problems else ""), when,
                         "Run .\\check-updates.ps1 in the dev folder" if state != "ok" else None))
    return out


@router.get("/system")
def system():
    """Every check, and the worst state among them (off counts as fine)."""
    now = datetime.now()
    checks = backup_checks(now, _read("status.json")) + other_checks(now)
    worst = max((c["state"] for c in checks), key=lambda s: ORDER[s], default="ok")
    return {"checks": checks, "worst": "ok" if worst == "off" else worst,
            "attention": [c for c in checks if c["state"] in ("warn", "bad")]}
