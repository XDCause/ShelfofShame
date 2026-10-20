# Dev with made-up sample data instead of a copy of prod's: an invented "Alex" with kits, games, hikes, a trip...
# (e2e\sample_data.py - the same data the showcase uses), so every page has something on it to look at and change.
#
#   .\sample-data.ps1          # dev's data replaced with the sample (dev only - it refuses to run on prod)
#   .\dev.ps1 -Refresh         # back to a copy of prod's real data
#
# Kept: your dev sign-in (password, authenticator, passkeys, devices) and the name Home greets you with. Dev's data is
# backed up first (backups\hobby_inventory_<time>_before_sample.dump). The sample is put in through the API with a
# sign-in made for the run (deleted after) - no password is needed or used. Dates are relative to today.
# ASCII only (Windows PowerShell 5.1).

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root

if ($AppEnv -ne 'dev') { Write-Host "This replaces the app's data - it only runs in the dev copy (this is $AppEnv)." -ForegroundColor Red; exit 1 }
if (-not (Test-Healthy $DbContainer) -or -not (Test-Healthy $ApiContainer) -or -not (Test-Healthy $WebContainer)) {
    Write-Host 'Dev is not running: start it with .\dev.ps1 first.' -ForegroundColor Red; exit 1
}
$image = 'offtheclock-e2e:1.47.0'
$quiet = @('-e', 'PGOPTIONS=-c client_min_messages=warning')
function Sql([string]$q) { (docker exec @quiet $DbContainer psql -U $DbUser -d $DbName -Atq -v ON_ERROR_STOP=1 -c $q) -join "`n" }

# 1. A backup of dev as it is now.
New-Item -ItemType Directory -Force backups | Out-Null
$backup = "backups\hobby_inventory_$(Get-Date -Format 'yyyyMMdd_HHmmss')_before_sample.dump"
Write-Host "Backing up dev to $backup..." -ForegroundColor Cyan
docker exec $DbContainer pg_dump -U $DbUser -d $DbName -Fc -f /tmp/before.dump
if ($LASTEXITCODE -ne 0) { Write-Host 'Backup failed - nothing changed.' -ForegroundColor Red; exit 1 }
docker cp "${DbContainer}:/tmp/before.dump" $backup | Out-Null
docker exec $DbContainer rm -f /tmp/before.dump | Out-Null

# 2. What to keep: the sign-in tables, and your name.
$name = Sql "SELECT value FROM settings WHERE key = 'your_name'"
docker exec $DbContainer pg_dump -U $DbUser -d $DbName -a -t auth_account -t auth_passkeys -t auth_recovery_codes -t auth_sessions -f /tmp/auth.sql
if ($LASTEXITCODE -ne 0) { Write-Host 'Saving the sign-in failed - nothing changed.' -ForegroundColor Red; exit 1 }

# 3. An empty database, built from db\init like a brand-new install, with the sign-in put back.
Write-Host 'Emptying dev and building it fresh from db\init...' -ForegroundColor Cyan
Sql 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' | Out-Null
$files = @(Get-ChildItem db\init\*.sql | Sort-Object Name)
$script = foreach ($file in $files) { Get-Content $file.FullName -Raw }
($script -join "`n") | docker exec -i @quiet $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Building the database failed. Dev's data is in $backup (or .\dev.ps1 -Refresh)." -ForegroundColor Red; exit 1 }
$names = ($files | ForEach-Object { "('$($_.Name)')" }) -join ','
Sql "INSERT INTO schema_migrations (name) VALUES $names ON CONFLICT DO NOTHING" | Out-Null     # all applied: migrate.ps1 has nothing to do
docker exec @quiet $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -f /tmp/auth.sql | Out-Null
$authOk = $LASTEXITCODE -eq 0
docker exec $DbContainer rm -f /tmp/auth.sql | Out-Null
if (-not $authOk) { Write-Host 'Putting the sign-in back failed: set a password again with .\set-password.ps1.' -ForegroundColor Yellow }

# 4. The sample, through the API, signed in for this run only.
Write-Host 'Filling in the sample data...' -ForegroundColor Cyan
$token = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
$hash = -join ([System.Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($token)) | ForEach-Object { $_.ToString('x2') })
if ((Sql 'SELECT count(*) FROM auth_account') -eq '0') {
    Sql "INSERT INTO auth_account (account_id, password_hash) VALUES (1, 'not set') ON CONFLICT DO NOTHING" | Out-Null
}
Sql "INSERT INTO auth_sessions (token_hash, method, expires_at, user_agent) VALUES ('$hash', 'password', now() + interval '1 hour', 'sample data (temporary)')" | Out-Null
$sampleName = if ($name) { '-' } else { 'Alex' }
docker build -q -t $image e2e | Out-Null
$cookie = if ($AppEnv -eq 'prod') { 'otc_session' } else { "otc_session_$AppEnv" }     # its name in this copy (api/app/auth.py COOKIE)
docker run --rm --network "${Prefix}_default" -e "E2E_TOKEN=$token" -e "E2E_COOKIE=$cookie" -e 'BASE=https://web' -e "SAMPLE_NAME=$sampleName" `
    -v "${Root}\e2e:/e2e" $image python /e2e/sample_data.py
$ok = $LASTEXITCODE -eq 0
Sql "DELETE FROM auth_sessions WHERE token_hash = '$hash'" | Out-Null
if ($name) { Sql "INSERT INTO settings (key, value) VALUES ('your_name', '$($name -replace "'", "''")') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value" | Out-Null }
if (-not $ok) { Write-Host "Some of the sample didn't go in (above). Dev's data before is in $backup." -ForegroundColor Yellow; exit 1 }
Write-Host 'Dev now has the sample data. (.\dev.ps1 -Refresh to go back to a copy of prod''s.)' -ForegroundColor Green
