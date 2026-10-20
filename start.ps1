# Start Shelf of Shame (database, API, web app) and print where to find them.
# Usage (from this folder):  .\start.ps1
# Works in both copies (prod = this folder, dev = ..\hobby-inventory-dev): names come from .env.
# If blocked by execution policy:  powershell -ExecutionPolicy Bypass -File .\start.ps1

# Note: no $ErrorActionPreference = 'Stop' here. In Windows PowerShell 5.1 that turns any
# stderr output from docker (warnings, build progress) into a fatal error. We check
# $LASTEXITCODE after each docker command instead.
. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$containers = @($DbContainer, $ApiContainer, $WebContainer)

# 1. Docker Desktop running?  'docker info' fails if the engine is not up.
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker is not running. Start Docker Desktop, wait for it to say "Engine running", then re-run.' -ForegroundColor Red
    exit 1
}

# 2. .env present?
if (-not (Test-Path '.env')) {
    Write-Host 'No .env file. Copy .env.example to .env and set a password.' -ForegroundColor Red
    exit 1
}
$envVars = @{}
Get-Content '.env' | Where-Object { $_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$' } | ForEach-Object {
    $envVars[$Matches[1]] = $Matches[2].Trim()
}

# 3. Build the image and start the container in the background.
Write-Host "Building and starting ($AppEnv)..." -ForegroundColor Cyan
docker compose build
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make-cert.ps1')   # HTTPS certificate
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host 'docker compose up failed - see the messages above.' -ForegroundColor Red
    exit 1
}

# 4. Wait for every container's healthcheck to pass.
Write-Host -NoNewline 'Waiting for containers to become healthy'
$deadline = (Get-Date).AddSeconds(120)
do {
    Start-Sleep -Seconds 2
    $statuses = @{}
    foreach ($c in $containers) { $statuses[$c] = docker inspect --format '{{.State.Health.Status}}' $c }
    $notReady = @($containers | Where-Object { $statuses[$_] -ne 'healthy' })
    Write-Host -NoNewline '.'
} while ($notReady.Count -gt 0 -and (Get-Date) -lt $deadline)
Write-Host ''

if ($notReady.Count -gt 0) {
    foreach ($c in $notReady) {
        Write-Host "$c did not become healthy (status: $($statuses[$c])). Last log lines:" -ForegroundColor Red
        docker logs --tail 30 $c
    }
    exit 1
}

# 5. Where to find everything.
$port = if ($envVars['POSTGRES_PORT']) { $envVars['POSTGRES_PORT'] } else { '5433' }
$webPort = if ($envVars['WEB_PORT']) { $envVars['WEB_PORT'] } else { '8080' }
$apiPort = if ($envVars['API_PORT']) { $envVars['API_PORT'] } else { '8000' }
Write-Host ''
$httpsPort = if ($envVars['WEB_HTTPS_PORT']) { $envVars['WEB_HTTPS_PORT'] } else { '8443' }
Write-Host "Web app:   https://$($env:COMPUTERNAME.ToLower()).local:$httpsPort   (or https://localhost:$httpsPort)" -ForegroundColor Green
Write-Host "API docs:  http://localhost:$apiPort/api/docs" -ForegroundColor Green
Write-Host ''
Write-Host 'DBeaver connection details:' -ForegroundColor Green
Write-Host "  Host:     localhost"
Write-Host "  Port:     $port"
Write-Host "  Database: $($envVars['POSTGRES_DB'])"
Write-Host "  Username: $($envVars['POSTGRES_USER'])"
Write-Host "  Password: $($envVars['POSTGRES_PASSWORD'])"
Write-Host "  JDBC URL: jdbc:postgresql://localhost:$port/$($envVars['POSTGRES_DB'])"
