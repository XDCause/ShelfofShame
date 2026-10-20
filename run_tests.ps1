# Run the automated API tests.
#
#   .\run_tests.ps1               # everything
#   .\run_tests.ps1 -k wishlist   # only tests whose name matches
#
# Your real data is never touched:
#   1. A separate database, hobby_inventory_test, is rebuilt from scratch using db/init/*.sql
#      (so this also checks that a brand-new install still works) - all files in one psql session.
#   2. The tests run in a throwaway copy of the api container, using the code currently on disk
#      (mounted in), so the live app keeps running and you don't need to rebuild first.
#   3. tamiya.com is replaced by a fake inside the tests, so they're fast and offline.
#   .\run_tests.ps1 -Coverage     # + which API lines no test runs (api\coverage.txt; pytest-cov goes
#                                 into the throwaway test container only)
param([string]$k = '', [switch]$Coverage)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$db = $DbContainer
$testDb = 'hobby_inventory_test'

if ((docker inspect --format '{{.State.Health.Status}}' $db 2>$null) -ne 'healthy') {
    Write-Host "$db isn't running. Start everything with .\start.ps1 first." -ForegroundColor Red
    exit 1
}

$code = Get-CodeHash          # recorded if everything passes (promote.ps1 can then skip a re-run)
Write-Host "Building a fresh $testDb database..." -ForegroundColor Cyan
# PGOPTIONS hides Postgres's harmless "does not exist, skipping" notices.
$quiet = @('-e', 'PGOPTIONS=-c client_min_messages=warning')
docker exec @quiet $db psql -U hobby -d postgres -q -c "DROP DATABASE IF EXISTS $testDb" -c "CREATE DATABASE $testDb"
if ($LASTEXITCODE -ne 0) { exit 1 }
# Every file in one psql session (was one session per file: ~10 s). \echo before each file says how
# far it got, so a failure still names the file.
$files = @(Get-ChildItem db\init\*.sql | Sort-Object Name)
$script = foreach ($file in $files) { "\echo applying $($file.Name)"; Get-Content $file.FullName -Raw }
$applied = @(($script -join "`n") | docker exec -i @quiet $db psql -U hobby -d $testDb -q -v ON_ERROR_STOP=1)
if ($LASTEXITCODE -ne 0) {
    $last = ($applied | Where-Object { $_ -like 'applying *' } | Select-Object -Last 1) -replace '^applying ', ''
    Write-Host "  $last FAILED on a fresh database" -ForegroundColor Red
    exit 1
}
Write-Host "  $($files.Count) db\init files ok ($($files[0].Name) ... $($files[-1].Name))"

Write-Host 'Running tests...' -ForegroundColor Cyan
$pytestArgs = @('-q')
if ($k) { $pytestArgs += @('-k', $k) }
if ($Coverage) {
    $cmd = "pip install -q --disable-pip-version-check pytest-cov==6.1.1 && python -m pytest $($pytestArgs -join ' ') " +
           "--cov=app --cov-report=term-missing:skip-covered > /app/coverage.txt; s=`$?; tail -70 /app/coverage.txt; exit `$s"
    docker compose run --rm --no-deps --name "$Prefix-tests" `
        -e "POSTGRES_DB=$testDb" -v "${PSScriptRoot}\api:/app" api sh -c $cmd
} else {
    docker compose run --rm --no-deps --name "$Prefix-tests" `
        -e "POSTGRES_DB=$testDb" -v "${PSScriptRoot}\api:/app" `
        api python -m pytest @pytestArgs
}
$result = $LASTEXITCODE

docker exec $db psql -U hobby -d postgres -q -c "DROP DATABASE IF EXISTS $testDb" | Out-Null
if ($result -eq 0) {
    Write-Host 'All tests passed.' -ForegroundColor Green
    if (-not $k -and -not $Coverage) { Set-Stamp 'api' $code }   # only a full run counts
}
else { Write-Host 'Some tests FAILED (see above).' -ForegroundColor Red }
exit $result
