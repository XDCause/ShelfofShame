# Click through the whole app in a real (headless) browser - desktop and iPhone sizes.
#
#   .\run_e2e.ps1
#
# The walk-through adds, edits and deletes things, so it never runs against this copy's own app.
# Instead it starts a THROWAWAY copy next to it (hobby-e2e-db / -api / -web, on its own Docker
# network and volume) from:
#   - the images this copy is running (so it tests exactly what .\dev.ps1 built), and
#   - a fresh pg_dump of this copy's database (your real data, read only),
# with its own video and backup folders (.e2e\, git-ignored) and no daily syncs. When it ends -
# pass, fail or Ctrl+C - the throwaway copy and its volume are deleted. You can keep using the
# app while it runs: nothing you do is touched.
# Screenshots are saved to e2e\out\ (git-ignored).

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$image = 'offtheclock-e2e:1.47.0'    # e2e\Dockerfile: Playwright's image with its Python package installed
$code = Get-CodeHash
$built = (Get-Stamp 'built')[0]
$E2E = 'hobby-e2e'
$E2EVolume = 'hobby_e2e_pgdata'

docker build -q -t $image e2e | Out-Null    # cached after the first time: instant
if ($LASTEXITCODE -ne 0) { Write-Host 'Building the walk-through image failed.' -ForegroundColor Red; exit 1 }

# The throwaway copy's settings: compose reads these before .env (see docker-compose.yml).
$e2eEnv = @{
    APP_PREFIX = $E2E; DB_VOLUME = $E2EVolume; POSTGRES_PORT = '5436'; API_PORT = '8003'; WEB_PORT = '8083'
    MEDIA_PATH = './.e2e/media'; BACKUP_PATH = './.e2e/backups'; DAILY_SYNCS = 'off'; APP_ENV = $AppEnv
}
function In-E2E([scriptblock]$block) {
    foreach ($k in $e2eEnv.Keys) { Set-Item "Env:$k" $e2eEnv[$k] }
    try { & $block } finally { foreach ($k in $e2eEnv.Keys) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } }
}
# Safety: `down -v` deletes a volume, so make sure compose really means the throwaway one.
function Assert-E2EConfig {
    $cfg = (In-E2E { docker compose -p $E2E config --format json 2>$null }) -join "`n" | ConvertFrom-Json
    $volumes = @($cfg.volumes.PSObject.Properties | ForEach-Object { $_.Value.name })
    if ($cfg.name -ne $E2E -or $volumes.Count -ne 1 -or $volumes[0] -ne $E2EVolume) {
        Write-Host "Refusing to go on: compose resolved to project '$($cfg.name)', volumes '$($volumes -join ', ')'." -ForegroundColor Red
        exit 1
    }
}
function Remove-E2E { In-E2E { docker compose -p $E2E down -v --remove-orphans 2>$null | Out-Null } }

Assert-E2EConfig
New-Item -ItemType Directory -Force .e2e\media, .e2e\backups, e2e\out | Out-Null
Remove-Item e2e\out\*.png -ErrorAction SilentlyContinue
Remove-E2E                                       # leftovers from a run that was killed
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
# Saved under a backup's name in the copy's own backups folder, so Settings > Backups has one to list.
Remove-Item .e2e\backups\* -Force -ErrorAction SilentlyContinue
$dump = ".e2e\backups\hobby_inventory_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
docker cp "${DbContainer}:/tmp/e2e.dump" $dump | Out-Null
docker exec $DbContainer rm -f /tmp/e2e.dump | Out-Null

$result = 1
try {
    # 2. The throwaway copy, from the images this copy runs.
    foreach ($s in 'db', 'api', 'web') { docker tag "$Prefix-${s}:1.0" "$E2E-${s}:1.0" }
    In-E2E { docker compose -p $E2E up -d --no-build 2>$null | Out-Null }
    if (-not (Wait-Healthy @("$E2E-db", "$E2E-api", "$E2E-web"))) { throw 'The walk-through copy did not start.' }
    docker cp $dump "${E2E}-db:/tmp/data.dump" | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' "$E2E-db" `
        psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' "$E2E-db" pg_restore -U $DbUser -d $DbName --no-owner /tmp/data.dump
    if ($LASTEXITCODE -ne 0) { throw 'Loading the data into the walk-through copy failed.' }

    # 3. The walk-through, on the throwaway copy's network (http://web is its nginx).
    docker run --rm --network "${E2E}_default" --ipc=host `
        -v "${PSScriptRoot}\e2e:/e2e" -v "${PSScriptRoot}\e2e\out:/out" $image `
        python /e2e/walkthrough.py
    $result = $LASTEXITCODE
} catch {
    Write-Host $_ -ForegroundColor Red
} finally {
    Write-Host 'Removing the walk-through copy...' -ForegroundColor Cyan
    Remove-E2E
    foreach ($s in 'db', 'api', 'web') { docker rmi "$E2E-${s}:1.0" 2>$null | Out-Null }   # just the extra names
    Remove-Item .e2e\backups\* -Force -ErrorAction SilentlyContinue
}
# A pass counts for promote.ps1 only if the running app was built from the code on disk.
if ($result -eq 0) {
    if ($built -eq $code) { Set-Stamp 'e2e' $code }
    else { Write-Host 'Note: the running app was built from older code than is on disk (rebuild with .\dev.ps1), so this pass is not recorded for promote.ps1.' -ForegroundColor Yellow }
}
exit $result
