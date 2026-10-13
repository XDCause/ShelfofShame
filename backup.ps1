# Back up the Shelf of Shame database (supplies, wishlist, photos, barcodes - everything).
#
#   .\backup.ps1                      # backup into .\backups, keep the newest 14
#   .\backup.ps1 -Keep 30             # keep more
#   .\backup.ps1 -CopyTo "D:\Backups" # also copy each backup somewhere else (USB drive, OneDrive...)
#
# Restore (replaces the current data!):
#   docker cp .\backups\<file>.dump hobby-inventory-db:/tmp/restore.dump
#   docker exec hobby-inventory-db pg_restore -U hobby -d hobby_inventory --clean --if-exists /tmp/restore.dump
# (in the dev copy the container is hobby-dev-db; names come from .env via scripts\common.ps1)
#
# Format: pg_dump "custom" format (-Fc) - compressed, and restorable table by table.
# It's written inside the container and copied out with docker cp, so PowerShell never touches
# the bytes (Windows PowerShell 5.1's Out-File would add a BOM that can break a restore).
param(
    [int]$Keep = 14,
    [string]$CopyTo = ''
)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$container = $DbContainer
$folder = $BackupDir
New-Item -ItemType Directory -Force $folder | Out-Null
$name = "hobby_inventory_$(Get-Date -Format yyyyMMdd_HHmmss).dump"
$log = Join-Path $folder 'backup.log'

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding ascii
}

$state = docker inspect --format '{{.State.Health.Status}}' $container 2>$null
if ($state -ne 'healthy') {
    Log "FAILED: $container is not running/healthy (state: '$state'). Is Docker Desktop running?"
    exit 1
}

docker exec $container pg_dump -U $DbUser -d $DbName -Fc -f "/tmp/$name"
if ($LASTEXITCODE -ne 0) { Log 'FAILED: pg_dump returned an error'; exit 1 }
docker cp "${container}:/tmp/$name" (Join-Path $folder $name) | Out-Null
$copied = $LASTEXITCODE
docker exec $container rm -f "/tmp/$name" | Out-Null
if ($copied -ne 0) { Log 'FAILED: could not copy the backup out of the container'; exit 1 }

$size = [math]::Round((Get-Item (Join-Path $folder $name)).Length / 1KB)
Log "OK: $name ($size KB)"

if ($CopyTo) {
    try {
        New-Item -ItemType Directory -Force $CopyTo | Out-Null
        Copy-Item (Join-Path $folder $name) $CopyTo
        Log "Copied to $CopyTo"
    } catch {
        Log "WARNING: copy to $CopyTo failed: $($_.Exception.Message)"
    }
}

# Keep only the newest $Keep backups (older .sql backups from before this script are left alone).
Get-ChildItem $folder -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending |
    Select-Object -Skip $Keep | ForEach-Object {
        Remove-Item $_.FullName
        Log "Removed old backup $($_.Name)"
    }
