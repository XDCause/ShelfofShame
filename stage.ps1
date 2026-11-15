# The staging copy: the last stop before prod. Dev is where things are built; staging is the tested code on a FRESH
# copy of prod's real data, to look over (phone and PC) before it goes live. dev -> staging -> prod.
#
#   .\stage.ps1 -Setup     # first time: staging branch + ..\hobby-inventory-staging folder + its .env, started
#                          # with a copy of prod's data
#   .\stage.ps1            # move dev's tested commits to staging: tests (unless they passed on this exact code),
#                          # staging fast-forwards to dev, a fresh copy of prod's data, its database changes, rebuild
#   .\stage.ps1 -Refresh   # just give staging a fresh copy of prod's data (prod is only read)
#   .\stage.ps1 -Stop      # stop the staging copy (its data is kept)
#
#                prod                          staging                               dev
#   folder       hobby-inventory               hobby-inventory-staging               hobby-inventory-dev
#   branch       main                          staging                               dev
#   web app      https://<pc>.local:8443       https://<pc>.local:8445 (STAGING)     https://<pc>.local:8444 (DEV)
#   API          localhost:8000                localhost:8002                        localhost:8001
#   database     5433, hobby_pgdata            5435, hobby_staging_pgdata            5434, hobby_dev_pgdata
#
# Staging has its own database, not dev's: dev's can be ahead (a database change still being built), and staging's
# job is to show the code on what prod will really have - so every stage starts from a fresh copy of prod's data.
# Staging runs no daily syncs or site checks (DAILY_SYNCS=off): prod already looks once a week.
# promote.ps1 then moves main to staging (when this copy exists) instead of straight to dev.
param([switch]$Setup, [switch]$Refresh, [switch]$Stop)
. "$PSScriptRoot\scripts\common.ps1"
$Base = $Root -replace '-(dev|staging)$', ''
$ProdRoot, $DevRoot, $StageRoot = $Base, "$Base-dev", "$Base-staging"
function Fail([string]$msg) { Write-Host $msg -ForegroundColor Red; exit 1 }
function Step([string]$msg) { Write-Host ''; Write-Host "== $msg" -ForegroundColor Cyan }
function In-Stage([scriptblock]$block) { Push-Location $StageRoot; try { & $block } finally { Pop-Location } }

function Start-Stage {
    Step 'Building and starting the staging copy'
    In-Stage { docker compose build 2>$null | Out-Null }
    if ($LASTEXITCODE -ne 0) { Fail 'The build failed - staging still runs the OLD code. Run "docker compose build" in the staging folder to see why.' }
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $StageRoot 'make-cert.ps1')
    if ($LASTEXITCODE -ne 0) { exit 1 }
    In-Stage { docker compose up -d 2>$null | Out-Null }
    if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed (run it in the staging folder to see why).' }
    Write-Host -NoNewline 'Waiting for it to be healthy'
    if (-not (Wait-Healthy @('hobby-staging-db', 'hobby-staging-api', 'hobby-staging-web'))) { exit 1 }
}

function Refresh-Stage {
    Step "A fresh copy of prod's data"
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProdRoot 'backup.ps1')
    if ($LASTEXITCODE -ne 0) { Fail 'Prod backup failed - staging not refreshed.' }
    $dump = Get-ChildItem (Join-Path $ProdRoot 'backups') -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending | Select-Object -First 1
    docker cp $dump.FullName 'hobby-staging-db:/tmp/prod.dump' | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' hobby-staging-db `
        psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' hobby-staging-db pg_restore -U $DbUser -d $DbName --no-owner /tmp/prod.dump
    $ok = $LASTEXITCODE -eq 0
    docker exec hobby-staging-db rm -f /tmp/prod.dump | Out-Null
    if (-not $ok) { Fail 'Restore into staging failed.' }
    Write-Host "Loaded $($dump.Name)."
    # the staging code's newer database changes, on top of prod's data - the same thing promote will do to prod
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $StageRoot 'migrate.ps1')
    if ($LASTEXITCODE -ne 0) { Fail "Staging's database changes failed on prod's data - fix them on dev before promoting." }
}

if ($Stop) { In-Stage { docker compose stop }; exit $LASTEXITCODE }

if ($Setup) {
    if (Test-Path $StageRoot) { Write-Host "$StageRoot already exists - skipping the checkout." -ForegroundColor Yellow }
    else {
        Push-Location $ProdRoot
        try {
            if (-not (git branch --list staging)) { git branch staging main }
            git worktree add $StageRoot staging
            if ($LASTEXITCODE -ne 0) { Fail 'git worktree add failed.' }
        } finally { Pop-Location }
    }
    # its .env: prod's (passwords, keys) with the staging copy's names, ports and settings
    $lines = Get-Content (Join-Path $ProdRoot '.env') | Where-Object {
        $_ -notmatch '^\s*(APP_PREFIX|APP_ENV|POSTGRES_PORT|API_PORT|WEB_PORT|WEB_HTTPS_PORT|DB_VOLUME|DAILY_SYNCS)\s*=' }
    $lines += @('', '# The staging copy (stage.ps1 wrote this)', 'APP_PREFIX=hobby-staging', 'APP_ENV=staging',
        'POSTGRES_PORT=5435', 'API_PORT=8002', 'WEB_PORT=8082', 'WEB_HTTPS_PORT=8445', 'DB_VOLUME=hobby_staging_pgdata', 'DAILY_SYNCS=off')
    [IO.File]::WriteAllLines((Join-Path $StageRoot '.env'), [string[]]$lines)
    Start-Stage
    Refresh-Stage
    Write-Host ''
    Write-Host 'Staging is ready: https://<this PC>.local:8445 (sign in with your usual password).' -ForegroundColor Green
    Write-Host 'The firewall may need port 8445 opened for phones on the home network (an admin step - yours to approve).'
    exit 0
}

if (-not (Test-Path $StageRoot)) { Fail "No staging copy yet: run .\stage.ps1 -Setup" }
if ($Refresh) { Refresh-Stage; Write-Host 'Staging now has a fresh copy of prod''s data.' -ForegroundColor Green; exit 0 }

# Stage: dev -> staging
if (git -C $DevRoot status --porcelain) { Fail 'The dev copy has uncommitted changes. Commit (or discard) them first.' }
if (git -C $StageRoot status --porcelain) { Fail 'The staging folder has uncommitted changes - it only takes commits from dev.' }
$commits = @(git -C $StageRoot log --oneline staging..dev)
if ($commits.Count -eq 0) { Write-Host 'Nothing to stage: staging already has everything on dev.' -ForegroundColor Green; exit 0 }
Step "$($commits.Count) change(s) to stage:"
$commits | ForEach-Object { Write-Host "  $_" }

# Tests on dev, unless every part already passed on exactly this code (the stamps run_tests / run_web_tests /
# run_e2e write in ..-dev\.tested)
$devTree = Get-TreeHash $DevRoot 'dev^{tree}'
$passed = @('api', 'web', 'e2e') | ForEach-Object { (Get-Stamp $_ $DevRoot)[0] -eq $devTree }
if ($passed -contains $false) {
    Step 'Tests on the dev copy'
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $DevRoot 'test_all.ps1')
    if ($LASTEXITCODE -ne 0) { Fail 'Tests failed on dev - staging not touched.' }
} else { Step 'Tests: already passed on exactly this code in dev - not run again' }

Step 'Moving staging to dev'
git -C $StageRoot merge --ff-only dev
if ($LASTEXITCODE -ne 0) { Fail 'staging has commits dev doesn''t (fast-forward impossible). Merge staging into dev, test, then stage.' }
Set-Stamp 'staged' $devTree $StageRoot          # what promote.ps1 checks: this exact code passed its tests
Start-Stage
Refresh-Stage
Write-Host ''
Write-Host "Staged $($commits.Count) change(s): staging is $(git -C $StageRoot rev-parse --short HEAD) on a fresh copy of prod's data." -ForegroundColor Green
Write-Host 'Look it over at https://<this PC>.local:8445, then .\promote.ps1 (in the prod folder) to put it live.'
