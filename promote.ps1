# Move tested changes from the dev copy to prod (your real data).
#
#   .\promote.ps1            # tests + browser walk-through on dev, then update prod
#   .\promote.ps1 -Quick     # API tests only on dev (skip the ~2 minute browser walk-through)
#   .\promote.ps1 -Push      # also push main and dev to GitHub afterwards
#   .\promote.ps1 -Retest    # run the tests even if they already passed on this exact code
#
# Run it in the prod folder (C:\Users\xdhar\hobby-inventory). Steps, stopping at the first problem:
#   1. checks: prod is on main with nothing uncommitted; dev has nothing uncommitted
#   2. shows the commits that will move (main..dev)
#   3. runs the API tests and the browser walk-through against the DEV copy, side by side - or skips
#      them if both already passed on exactly the code being promoted (stamps in ..-dev\.tested,
#      written by run_tests.ps1 / run_e2e.ps1; see scripts\common.ps1)
#   4. backs up prod
#   5. fast-forwards main to dev (git merge --ff-only: never a merge commit, never rewrites history)
#   6. applies new database changes to prod (migrate.ps1)
#   7. rebuilds and restarts prod, and waits until it's healthy
# If anything goes wrong after step 4, the end of the output says how to go back.
param([switch]$Quick, [switch]$Push, [switch]$Retest)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$DevRoot = "$Root-dev"

function Fail([string]$msg) { Write-Host $msg -ForegroundColor Red; exit 1 }
function Step([string]$msg) { Write-Host ''; Write-Host "== $msg" -ForegroundColor Cyan }

# 1. Checks
if ($AppEnv -ne 'prod') { Fail 'Run promote.ps1 in the prod folder, not the dev copy.' }
if ((git rev-parse --abbrev-ref HEAD) -ne 'main') { Fail 'The prod folder must be on the main branch.' }
if (git status --porcelain) { Fail 'The prod folder has uncommitted changes. Commit them on dev instead.' }
if (-not (Test-Path $DevRoot)) { Fail "No dev copy at $DevRoot. Set it up with .\dev.ps1 -Setup" }
if (git -C $DevRoot status --porcelain) { Fail 'The dev copy has uncommitted changes. Commit (or discard) them first.' }

# 2. What's moving
$commits = @(git log --oneline main..dev)
if ($commits.Count -eq 0) { Write-Host 'Nothing to promote: main already has everything on dev.' -ForegroundColor Green; exit 0 }
Step "$($commits.Count) change(s) to promote:"
$commits | ForEach-Object { Write-Host "  $_" }
$before = git rev-parse --short HEAD

# 3. Tests on dev - skipped when they already passed on exactly this code (dev is clean, checked above,
#    so the code on disk is the dev commit's tree)
$devTree = Get-TreeHash $DevRoot 'dev^{tree}'      # the dev commit's code, notes (*.md) left out
$api = Get-Stamp 'api' $DevRoot
$e2e = Get-Stamp 'e2e' $DevRoot
$passed = ($api[0] -eq $devTree) -and ($Quick -or $e2e[0] -eq $devTree)
if ($passed -and -not $Retest) {
    $when = if ($Quick) { $api[1] } else { @($api[1], $e2e[1]) | Sort-Object | Select-Object -First 1 }
    Step "Tests: already passed on exactly this code in dev (since $when) - not run again (-Retest to run them)"
} else {
    Step 'Tests on the dev copy (API tests and browser walk-through side by side)'
    $testArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $DevRoot 'test_all.ps1'))
    if ($Quick) { $testArgs += '-Quick' }
    powershell @testArgs
    if ($LASTEXITCODE -ne 0) { Fail 'Tests failed on dev - prod not touched.' }
}

# 4. Backup
Step 'Backing up prod'
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'backup.ps1')
if ($LASTEXITCODE -ne 0) { Fail 'Backup failed - prod not touched.' }
$backup = (Get-ChildItem $BackupDir -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending | Select-Object -First 1).Name

$rollback = @"

To go back to how prod was before this promote:
  git reset --hard $before
  docker cp .\backups\$backup ${DbContainer}:/tmp/restore.dump
  docker exec $DbContainer pg_restore -U $DbUser -d $DbName --clean --if-exists /tmp/restore.dump
  docker compose up -d --build
"@

# 5. Code
Step 'Moving main to dev'
git merge --ff-only dev
if ($LASTEXITCODE -ne 0) { Fail 'main has commits dev doesn''t (fast-forward impossible) - prod not touched. Merge main into dev, test, then promote.' }

# 6. Database
Step 'Database changes'
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'migrate.ps1')
if ($LASTEXITCODE -ne 0) { Fail ("Database update failed.$rollback") }

# 7. Rebuild
Step 'Rebuilding and restarting prod'
docker compose up -d --build 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail ("docker compose up failed.$rollback") }
Write-Host -NoNewline 'Waiting for prod to be healthy'
if (-not (Wait-Healthy @($DbContainer, $ApiContainer, $WebContainer))) { Fail ("Prod didn't come back healthy.$rollback") }

if ($Push) {
    Step 'Pushing to GitHub'
    git push origin main dev
}

Write-Host ''
Write-Host "Promoted $($commits.Count) change(s): prod is now $(git rev-parse --short HEAD) (was $before)." -ForegroundColor Green
Write-Host "Backup taken just before: backups\$backup"
Write-Host $rollback
