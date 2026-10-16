# Back up the database (everything you've entered, with its photos) and your uploaded videos.
#
#   .\backup.ps1                      # backup into .\backups, keep the newest 14
#   .\backup.ps1 -Keep 30             # keep more
#   .\backup.ps1 -CopyTo "D:\Backups" # also copy each backup somewhere else (USB drive, OneDrive...)
#
# The nightly task copies to the network drive on the modem (a slow, sometimes flaky share - about
# 2 MB/s): \\10.0.0.138\Seagate_ExpansionDesk_2_917f\Off the Clock backups. That copy keeps the newest
# $Keep backups too. If the drive can't be reached, the backup here still counts; the log says so.
#
# Restore (replaces the current data!):
#   docker cp .\backups\<file>.dump hobby-inventory-db:/tmp/restore.dump
#   docker exec hobby-inventory-db pg_restore -U hobby -d hobby_inventory --clean --if-exists /tmp/restore.dump
# (in the dev copy the container is hobby-dev-db; names come from .env via scripts\common.ps1)
#
# Videos (the media folder - too big for the database) are copied to backups\media: only new ones
# each time (a video never changes once uploaded). Videos deleted in the app stay in the backup, so
# a mistaken delete can be undone. To restore them: copy backups\media back over media.
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

# Uploaded videos: copy the new ones (robocopy /E = with subfolders; /XC /XN /XO = skip files the
# backup already has). Robocopy's exit codes 0-7 mean success, 8 and up mean something failed.
# To a network drive (-Slow): /Z = restartable (a dropped connection carries on where it stopped),
# 3 tries 30 s apart, and /IPG = a short gap between chunks so the modem's file sharing keeps up.
function Copy-Media($to, [switch]$Slow) {
    $media = Join-Path $Root 'media'
    if (-not (Test-Path $media)) { return }
    $extra = if ($Slow) { @('/Z', '/R:3', '/W:30', '/IPG:5') } else { @('/R:1', '/W:1') }
    robocopy $media $to /E /XC /XN /XO @extra /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Log "WARNING: copying videos to $to failed (robocopy $LASTEXITCODE)"; return }
    $files = Get-ChildItem $to -Recurse -File -ErrorAction SilentlyContinue
    $mb = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB)
    Log "OK: videos in $to - $(@($files).Count) files, $mb MB"
}
Copy-Media (Join-Path $folder 'media')

if ($CopyTo) {
    try {
        New-Item -ItemType Directory -Force $CopyTo | Out-Null
        Copy-Item (Join-Path $folder $name) $CopyTo -ErrorAction Stop
        $same = (Get-FileHash (Join-Path $folder $name)).Hash -eq (Get-FileHash (Join-Path $CopyTo $name)).Hash
        if ($same) { Log "Copied to $CopyTo (checked: identical)" } else { Log "WARNING: the copy in $CopyTo doesn't match" }
        Get-ChildItem $CopyTo -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending |
            Select-Object -Skip $Keep | ForEach-Object { Remove-Item $_.FullName; Log "Removed old copy $($_.Name) from $CopyTo" }
        Copy-Media (Join-Path $CopyTo 'media') -Slow:($CopyTo -like '\\*')
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
