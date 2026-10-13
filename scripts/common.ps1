# Shared by the .ps1 scripts in the project folder (dot-source it: . "$PSScriptRoot\scripts\common.ps1").
#
# Reads this copy's .env and works out its names, so every script works in both copies:
#   prod  (this folder, main branch)               hobby-inventory-db / -api / -web, web on 8080
#   dev   (..\hobby-inventory-dev, dev branch)     hobby-dev-db / -api / -web, web on 8081
# ASCII only: Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI.

$Root = Split-Path -Parent $PSScriptRoot   # this file is in <project>\scripts

function Read-DotEnv([string]$path) {
    $values = @{}
    if (Test-Path $path) {
        Get-Content $path | Where-Object { $_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$' } | ForEach-Object {
            $values[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $values
}

$Cfg = Read-DotEnv (Join-Path $Root '.env')
function Cfg([string]$key, [string]$default) { if ($Cfg[$key]) { $Cfg[$key] } else { $default } }

$Prefix = Cfg 'APP_PREFIX' 'hobby-inventory'
$AppEnv = Cfg 'APP_ENV' 'prod'
$DbContainer = "$Prefix-db"
$ApiContainer = "$Prefix-api"
$WebContainer = "$Prefix-web"
$Network = "${Prefix}_default"      # compose project name = APP_PREFIX
$DbName = Cfg 'POSTGRES_DB' 'hobby_inventory'
$DbUser = Cfg 'POSTGRES_USER' 'hobby'
$WebPort = Cfg 'WEB_PORT' '8080'
$ApiPort = Cfg 'API_PORT' '8000'
$DbPort = Cfg 'POSTGRES_PORT' '5433'
$BackupDir = Join-Path $Root 'backups'

function Test-Healthy([string]$container) {
    return (docker inspect --format '{{.State.Health.Status}}' $container 2>$null) -eq 'healthy'
}

function Wait-Healthy([string[]]$containers, [int]$seconds = 120) {
    $deadline = (Get-Date).AddSeconds($seconds)
    do {
        Start-Sleep -Seconds 2
        $notReady = @($containers | Where-Object { -not (Test-Healthy $_) })
        Write-Host -NoNewline '.'
    } while ($notReady.Count -gt 0 -and (Get-Date) -lt $deadline)
    Write-Host ''
    foreach ($c in $notReady) {
        Write-Host "$c did not become healthy. Last log lines:" -ForegroundColor Red
        docker logs --tail 30 $c
    }
    return $notReady.Count -eq 0
}
