# The dev copy: a second, separate Shelf of Shame for trying out changes before they reach prod.
#
#   .\dev.ps1 -Setup     # first time: dev branch + ..\hobby-inventory-dev folder + its .env,
#                        # start it, and fill it with a copy of prod's data
#   .\dev.ps1            # (re)build and start the dev copy with the code in its folder
#   .\dev.ps1 -Refresh   # replace dev's data with a fresh copy of prod's (prod is only read)
#   .\dev.ps1 -Stop      # stop the dev copy (its data is kept)
#
#                prod (real data)                     dev (test copy)
#   folder       C:\Users\xdhar\hobby-inventory       C:\Users\xdhar\hobby-inventory-dev
#   git branch   main                                 dev
#   web app      http://localhost:8080                http://localhost:8081  (DEV badge)
#   API          http://localhost:8000/api/docs       http://localhost:8001/api/docs
#   database     localhost:5433, volume hobby_pgdata  localhost:5434, volume hobby_dev_pgdata
#
# The dev folder is a git "worktree": a second checkout of the same repository, so commits made
# there are on the dev branch and promote.ps1 can move them to main. Run from either folder.
param([switch]$Setup, [switch]$Refresh, [switch]$Stop)

. "$PSScriptRoot\scripts\common.ps1"
if ($AppEnv -eq 'dev') { $DevRoot = $Root; $ProdRoot = $Root -replace '-dev$', '' }
else { $ProdRoot = $Root; $DevRoot = "$Root-dev" }

function In-Dev([scriptblock]$block) {
    Push-Location $DevRoot
    try { & $block } finally { Pop-Location }
}

function Start-Dev {
    Write-Host 'Building and starting the dev copy...' -ForegroundColor Cyan
    In-Dev { docker compose up -d --build 2>$null | Out-Null }
    if ($LASTEXITCODE -ne 0) { Write-Host 'docker compose up failed (run it in the dev folder to see why).' -ForegroundColor Red; exit 1 }
    Write-Host -NoNewline 'Waiting for it to be healthy'
    if (-not (Wait-Healthy @('hobby-dev-db', 'hobby-dev-api', 'hobby-dev-web'))) { exit 1 }
}

function Refresh-Dev {
    Write-Host 'Backing up prod to copy its data...' -ForegroundColor Cyan
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProdRoot 'backup.ps1')
    if ($LASTEXITCODE -ne 0) { Write-Host 'Prod backup failed - dev not refreshed.' -ForegroundColor Red; exit 1 }
    $dump = Get-ChildItem (Join-Path $ProdRoot 'backups') -Filter 'hobby_inventory_*.dump' |
        Sort-Object Name -Descending | Select-Object -First 1
    Write-Host "Loading $($dump.Name) into the dev database..." -ForegroundColor Cyan
    docker cp $dump.FullName 'hobby-dev-db:/tmp/prod.dump' | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' hobby-dev-db `
        pg_restore -U $DbUser -d $DbName --clean --if-exists --no-owner /tmp/prod.dump
    $ok = $LASTEXITCODE -eq 0
    docker exec hobby-dev-db rm -f /tmp/prod.dump | Out-Null
    if (-not $ok) { Write-Host 'Restore into dev failed.' -ForegroundColor Red; exit 1 }
    # Dev may be ahead of prod: apply dev's newer db\init files to the copied data.
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $DevRoot 'migrate.ps1')
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Write-Host 'Dev now has a copy of prod''s data.' -ForegroundColor Green
}

if ($Stop) {
    In-Dev { docker compose stop }
    exit $LASTEXITCODE
}

if ($Setup) {
    if (Test-Path $DevRoot) {
        Write-Host "$DevRoot already exists - skipping the checkout." -ForegroundColor Yellow
    } else {
        Push-Location $ProdRoot
        git show-ref --verify --quiet refs/heads/dev
        if ($LASTEXITCODE -ne 0) { git branch dev main }
        git worktree add $DevRoot dev
        $made = $LASTEXITCODE
        Pop-Location
        if ($made -ne 0) { Write-Host 'git worktree add failed.' -ForegroundColor Red; exit 1 }
    }
    $devEnv = Join-Path $DevRoot '.env'
    if (-not (Test-Path $devEnv)) {
        # Same database name, user and password as prod; its own names, ports and data volume.
        $lines = Get-Content (Join-Path $ProdRoot '.env') | Where-Object {
            $_ -notmatch '^\s*(APP_PREFIX|APP_ENV|POSTGRES_PORT|API_PORT|WEB_PORT|DB_VOLUME)\s*='
        }
        $lines += @('', '# The dev copy (dev.ps1 wrote this)', 'APP_PREFIX=hobby-dev', 'APP_ENV=dev',
                    'POSTGRES_PORT=5434', 'API_PORT=8001', 'WEB_PORT=8081', 'DB_VOLUME=hobby_dev_pgdata')
        Set-Content -Path $devEnv -Value $lines -Encoding ascii
        Write-Host "Wrote $devEnv" -ForegroundColor Green
    }
    Start-Dev
    Refresh-Dev
} elseif ($Refresh) {
    Refresh-Dev
} else {
    Start-Dev
}

Write-Host ''
Write-Host 'Dev copy:  http://localhost:8081   (API docs: http://localhost:8001/api/docs)' -ForegroundColor Green
Write-Host "Code:      $DevRoot  (branch dev).  Promote to prod with .\promote.ps1"
