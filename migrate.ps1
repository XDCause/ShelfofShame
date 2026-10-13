# Bring this copy's database up to date with db\init\*.sql.
#
#   .\migrate.ps1            # apply every file the database hasn't had yet, in order
#   .\migrate.ps1 -List      # just show what's applied and what's pending
#
# The table schema_migrations (db\init\17_schema_migrations.sql) lists the files a database has
# had. Each pending file runs in its own psql session and stops at the first error; it's only
# recorded once it succeeded. Back up first (promote.ps1 does) - this changes the database.
# Works in prod and dev: names come from .env (scripts\common.ps1).
param([switch]$List)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$quiet = @('-e', 'PGOPTIONS=-c client_min_messages=warning')

if (-not (Test-Healthy $DbContainer)) {
    Write-Host "$DbContainer isn't running." -ForegroundColor Red
    exit 1
}

function Sql([string]$query) {
    $out = docker exec @quiet $DbContainer psql -U $DbUser -d $DbName -tA -c $query
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $query" }
    return $out
}

function Apply([System.IO.FileInfo]$file) {
    Get-Content $file.FullName -Raw | docker exec -i @quiet $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 | Out-Null
    return $LASTEXITCODE -eq 0
}

$files = Get-ChildItem (Join-Path $Root 'db\init\*.sql') | Sort-Object Name

# First run on a database from before migrations were tracked: 17 records itself and 01-16.
if ((Sql "SELECT to_regclass('schema_migrations') IS NOT NULL") -ne 't') {
    $bootstrap = $files | Where-Object Name -eq '17_schema_migrations.sql'
    if ($List) { Write-Host 'schema_migrations is missing: 17_schema_migrations.sql would set it up.'; exit 0 }
    Write-Host 'Setting up migration tracking (17_schema_migrations.sql)...' -ForegroundColor Cyan
    if (-not (Apply $bootstrap)) { Write-Host 'FAILED.' -ForegroundColor Red; exit 1 }
}

$applied = @(Sql 'SELECT name FROM schema_migrations')
$pending = @($files | Where-Object { $applied -notcontains $_.Name })

if ($List) {
    foreach ($f in $files) {
        $mark = if ($applied -contains $f.Name) { 'applied' } else { 'PENDING' }
        Write-Host ("  {0,-8} {1}" -f $mark, $f.Name)
    }
    exit 0
}

if ($pending.Count -eq 0) {
    Write-Host "$DbName ($AppEnv) is up to date." -ForegroundColor Green
    exit 0
}
foreach ($f in $pending) {
    if (-not (Apply $f)) {
        Write-Host "  $($f.Name) FAILED - stopped here. Nothing after it was applied." -ForegroundColor Red
        exit 1
    }
    Sql "INSERT INTO schema_migrations (name) VALUES ('$($f.Name)') ON CONFLICT DO NOTHING" | Out-Null
    Write-Host "  $($f.Name) applied"
}
Write-Host "$DbName ($AppEnv) is up to date." -ForegroundColor Green
