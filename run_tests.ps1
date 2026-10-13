# Run the automated API tests.
#
#   .\run_tests.ps1               # everything
#   .\run_tests.ps1 -k wishlist   # only tests whose name matches
#
# Your real data is never touched:
#   1. A separate database, hobby_inventory_test, is rebuilt from scratch using db/init/*.sql
#      (so this also checks that a brand-new install still works).
#   2. The tests run in a throwaway copy of the api container, using the code currently on disk
#      (mounted in), so the live app keeps running and you don't need to rebuild first.
#   3. tamiya.com is replaced by a fake inside the tests, so they're fast and offline.
param([string]$k = '')

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$db = $DbContainer
$testDb = 'hobby_inventory_test'

if ((docker inspect --format '{{.State.Health.Status}}' $db 2>$null) -ne 'healthy') {
    Write-Host "$db isn't running. Start everything with .\start.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Building a fresh $testDb database..." -ForegroundColor Cyan
# PGOPTIONS hides Postgres's harmless "does not exist, skipping" notices.
$quiet = @('-e', 'PGOPTIONS=-c client_min_messages=warning')
docker exec @quiet $db psql -U hobby -d postgres -q -c "DROP DATABASE IF EXISTS $testDb" -c "CREATE DATABASE $testDb"
if ($LASTEXITCODE -ne 0) { exit 1 }
foreach ($file in Get-ChildItem db\init\*.sql | Sort-Object Name) {
    Get-Content $file.FullName -Raw | docker exec -i @quiet $db psql -U hobby -d $testDb -q -v ON_ERROR_STOP=1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "  $($file.Name) FAILED on a fresh database" -ForegroundColor Red; exit 1 }
    Write-Host "  $($file.Name) ok"
}

Write-Host 'Running tests...' -ForegroundColor Cyan
$pytestArgs = @('-q')
if ($k) { $pytestArgs += @('-k', $k) }
docker compose run --rm --no-deps --name "$Prefix-tests" `
    -e "POSTGRES_DB=$testDb" -v "${PSScriptRoot}\api:/app" `
    api python -m pytest @pytestArgs
$result = $LASTEXITCODE

docker exec $db psql -U hobby -d postgres -q -c "DROP DATABASE IF EXISTS $testDb" | Out-Null
if ($result -eq 0) { Write-Host 'All tests passed.' -ForegroundColor Green }
else { Write-Host 'Some tests FAILED (see above).' -ForegroundColor Red }
exit $result
