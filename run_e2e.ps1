# Click through the whole app in a real (headless) browser - desktop and iPhone sizes - and audit every page.
#
#   .\run_e2e.ps1              # the walk-through and the UI audit, side by side (~5-6 minutes)
#   .\run_e2e.ps1 -NoAudit     # the walk-through only (quicker, while working on something; promote runs both)
#
# Neither runs against this copy's own app. Each gets a THROWAWAY copy next to it, started from:
#   - the images this copy is running (so it tests exactly what .\dev.ps1 built), and
#   - a fresh pg_dump of this copy's database (your real data, read only),
# with no daily syncs, stand-ins for every outside site, and its own password (a new one each run: the copy's account
# is reset - yours is never used or seen). Two copies because the walk-through changes data while the audit is
# looking at pages: separate copies keep both steady, and lets them run at the same time.
#   hobby-e2e-*    the walk-through (e2e\walkthrough.py)
#   hobby-e2ea-*   the UI audit (e2e\ui_audit.py: every page at 5 sizes x 2 themes - overflow, clipped or overlapping
#                  text, touch targets, broken pictures, axe-core accessibility, browser errors)
# When it ends - pass, fail or Ctrl+C - both copies and their volumes are deleted. You can keep using the app while
# it runs. Screenshots go to e2e\out\ (git-ignored).
param([switch]$NoAudit)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$image = 'offtheclock-e2e:1.47.0'    # e2e\Dockerfile: Playwright's image with its Python packages installed
$code = Get-CodeHash
$built = (Get-Stamp 'built')[0]

docker build -q -t $image e2e | Out-Null    # cached after the first time: instant
if ($LASTEXITCODE -ne 0) { Write-Host 'Building the walk-through image failed.' -ForegroundColor Red; exit 1 }

# The throwaway copies' settings: compose reads these before .env (see docker-compose.yml).
$copies = @(
    @{ Name = 'hobby-e2e'; Volume = 'hobby_e2e_pgdata'; Db = '5436'; Api = '8003'; Web = '8083'; Https = '8446'; Run = 'walkthrough.py' }
)
if (-not $NoAudit) {
    $copies += @{ Name = 'hobby-e2ea'; Volume = 'hobby_e2ea_pgdata'; Db = '5437'; Api = '8004'; Web = '8084'; Https = '8447'; Run = 'ui_audit.py' }
}
function In-Copy($c, [scriptblock]$block) {
    $vars = @{
        APP_PREFIX = $c.Name; DB_VOLUME = $c.Volume; POSTGRES_PORT = $c.Db; API_PORT = $c.Api; WEB_PORT = $c.Web; WEB_HTTPS_PORT = $c.Https
        MEDIA_PATH = './.e2e/media'; BACKUP_PATH = './.e2e/backups'; DAILY_SYNCS = 'off'; APP_ENV = $AppEnv
        OUTSIDE_SITES = 'stand-ins'     # no live calls to any outside site (api/app/stand_ins.py)
    }
    foreach ($k in $vars.Keys) { Set-Item "Env:$k" $vars[$k] }
    try { & $block } finally { foreach ($k in $vars.Keys) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } }
}
# Safety: `down -v` deletes a volume, so make sure compose really means the throwaway one.
function Assert-CopyConfig($c) {
    $cfg = (In-Copy $c { docker compose -p $c.Name config --format json 2>$null }) -join "`n" | ConvertFrom-Json
    $volumes = @($cfg.volumes.PSObject.Properties | ForEach-Object { $_.Value.name })
    if ($cfg.name -ne $c.Name -or $volumes.Count -ne 1 -or $volumes[0] -ne $c.Volume) {
        Write-Host "Refusing to go on: compose resolved to project '$($cfg.name)', volumes '$($volumes -join ', ')'." -ForegroundColor Red
        exit 1
    }
}
function Remove-Copy($c) {
    In-Copy $c { docker compose -p $c.Name down -v --remove-orphans 2>$null | Out-Null }
    foreach ($s in 'db', 'api', 'web') { docker rmi "$($c.Name)-${s}:1.0" 2>$null | Out-Null }   # just the extra names
}

foreach ($c in $copies) { Assert-CopyConfig $c }
New-Item -ItemType Directory -Force .e2e\media, .e2e\backups, e2e\out | Out-Null
Remove-Item e2e\out\*.png -ErrorAction SilentlyContinue
foreach ($c in $copies) { docker rm -f "$($c.Name)-run" 2>$null | Out-Null; Remove-Copy $c }   # leftovers from a killed run
# Your videos, as hard links (same files, no copying, no extra space): deleting a link in the
# walk-through leaves your file alone.
Remove-Item .e2e\media\* -Recurse -Force -ErrorAction SilentlyContinue
$mediaRoot = (Resolve-Path media -ErrorAction SilentlyContinue).Path
if ($mediaRoot) {
    Get-ChildItem $mediaRoot -File -Recurse | Where-Object { $_.Extension -ne '.part' } | ForEach-Object {
        $link = Join-Path '.e2e\media' $_.FullName.Substring($mediaRoot.Length + 1)     # media\videos\x.mp4 -> .e2e\media\videos\x.mp4
        New-Item -ItemType Directory -Force (Split-Path $link) | Out-Null
        New-Item -ItemType HardLink -Path $link -Target $_.FullName | Out-Null
    }
}

# 1. A copy of this copy's data (pg_dump only reads).
Write-Host "Copying $AppEnv's data for the walk-through..." -ForegroundColor Cyan
docker exec $DbContainer pg_dump -U $DbUser -d $DbName -Fc -f /tmp/e2e.dump
if ($LASTEXITCODE -ne 0) { Write-Host 'Copying the data failed.' -ForegroundColor Red; exit 1 }
# Saved under a backup's name in the copies' backups folder, so Settings > Backups has one to list.
Remove-Item .e2e\backups\* -Force -ErrorAction SilentlyContinue
$dump = ".e2e\backups\hobby_inventory_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
docker cp "${DbContainer}:/tmp/e2e.dump" $dump | Out-Null
docker exec $DbContainer rm -f /tmp/e2e.dump | Out-Null

$result = 1
try {
    # 2. The throwaway copies, from the images this copy runs: started, loaded with the data, given a password.
    $password = 'walk-through ' + [guid]::NewGuid().ToString('N')     # this run's own (never yours)
    foreach ($c in $copies) {
        foreach ($s in 'db', 'api', 'web') { docker tag "$Prefix-${s}:1.0" "$($c.Name)-${s}:1.0" }
        In-Copy $c { docker compose -p $c.Name up -d --no-build 2>$null | Out-Null }
    }
    foreach ($c in $copies) {
        $n = $c.Name
        if (-not (Wait-Healthy @("$n-db", "$n-api", "$n-web"))) { throw "The copy $n did not start." }
        docker cp $dump "${n}-db:/tmp/data.dump" | Out-Null
        docker exec -e 'PGOPTIONS=-c client_min_messages=warning' "$n-db" `
            psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' | Out-Null
        docker exec -e 'PGOPTIONS=-c client_min_messages=warning' "$n-db" pg_restore -U $DbUser -d $DbName --no-owner /tmp/data.dump
        if ($LASTEXITCODE -ne 0) { throw "Loading the data into $n failed." }
        $password | docker exec -i "$n-api" python -m app.auth set-password --stdin --reset-authenticator --sign-out-everywhere | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Setting $n's password failed." }
    }

    # 3. The walk-through and the audit, side by side, each on its copy's network (https://web is its nginx).
    if ($copies.Count -gt 1) { Write-Host 'Walk-through and UI audit (every page, 5 sizes x 2 themes), side by side...' -ForegroundColor Cyan }
    foreach ($c in $copies) {
        docker run -d --name "$($c.Name)-run" --network "$($c.Name)_default" --ipc=host -e "E2E_PASSWORD=$password" `
            -v "${PSScriptRoot}\e2e:/e2e" -v "${PSScriptRoot}\e2e\out:/out" $image python "/e2e/$($c.Run)" | Out-Null
    }
    $result = 0
    foreach ($c in $copies) {
        $exit = [int](docker wait "$($c.Name)-run")
        Write-Host ''
        Write-Host "----- $($c.Run) (exit $exit) -----" -ForegroundColor Cyan
        docker logs "$($c.Name)-run" 2>&1 | ForEach-Object { "$_" }
        docker rm "$($c.Name)-run" 2>$null | Out-Null
        if ($exit -ne 0) { $result = $exit }
    }
} catch {
    Write-Host $_ -ForegroundColor Red
    $result = 1
} finally {
    Write-Host 'Removing the throwaway copies...' -ForegroundColor Cyan
    foreach ($c in $copies) { docker rm -f "$($c.Name)-run" 2>$null | Out-Null; Remove-Copy $c }
    Remove-Item .e2e\backups\* -Force -ErrorAction SilentlyContinue
}
# A pass counts for promote.ps1 only if the running app was built from the code on disk, and the audit ran too.
if ($result -eq 0) {
    if ($NoAudit) { Write-Host 'Note: -NoAudit, so this pass is not recorded for promote.ps1 (it runs the audit too).' -ForegroundColor Yellow }
    elseif ($built -eq $code) { Set-Stamp 'e2e' $code }
    else { Write-Host 'Note: the running app was built from older code than is on disk (rebuild with .\dev.ps1), so this pass is not recorded for promote.ps1.' -ForegroundColor Yellow }
}
exit $result
