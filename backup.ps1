# Back up the database (everything you've entered, with its photos) and your uploaded videos.
#
#   .\backup.ps1                      # backup into .\backups, keep the newest 14
#   .\backup.ps1 -Keep 30             # keep more
#   .\backup.ps1 -CopyTo "D:\Backups" # also copy each backup somewhere else (USB drive, network drive...)
#   .\backup.ps1 -TestRestore         # also do the weekly test restore now
#
# Until 2026-10-22 the nightly task also copied to a drive on the modem; it slept and failed four nights unnoticed,
# so it was retired and Google Drive (below) holds the whole backup. -CopyTo still works for any other folder (it
# wakes a sleeping network share first, keeps the newest $Keep backups there too, and says so if it fails).
#
# Every backup is checked (health check, 2026-10-21):
#   - read back: pg_restore --list must read it, and the copy on disk must match the one Postgres wrote;
#   - once a week (or -TestRestore): restored for real into a throwaway database, every table's row count
#     compared with the live one, then the throwaway database dropped.
#   Each result goes in backups\backup.log and backups\status.json (Settings > System and Home read it).
#
# Off-site (prod only, once set up with .\setup-offsite.ps1): each backup is encrypted (gpg, AES-256, your
# password) and copied to a folder Google Drive for desktop syncs. Kept there: the last 7 days, one a week for
# 4 weeks, one a month for 6 months (about 11 MB each), never more than OffsiteBudgetMB. The videos go too, each
# encrypted once (about 5 GB of the 15 GB Google gives you; a new video adds its size). To get either back:
# .\restore-offsite.ps1 -File <a backup> or -Videos <the Drive folder>. A failure pops up a Windows notification.
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
    [string]$CopyTo = '',
    [switch]$TestRestore,
    [int]$OffsiteBudgetMB = 2048
)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$container = $DbContainer
$folder = $BackupDir
New-Item -ItemType Directory -Force $folder | Out-Null
$name = "hobby_inventory_$(Get-Date -Format yyyyMMdd_HHmmss).dump"
$log = Join-Path $folder 'backup.log'
$statusFile = Join-Path $folder 'status.json'
$now = Get-Date -Format 's'

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding ascii
}

# status.json: one object, each part updated by name (the API reads it; ASCII, so 5.1 writes it plainly).
function Read-Status {
    if (Test-Path $statusFile) { try { return Get-Content $statusFile -Raw | ConvertFrom-Json } catch { } }
    return New-Object PSObject
}
# A Windows notification on this PC (the nightly task runs while you're signed in): a failure shows the morning after,
# not only inside the app. (2026-10-22: the network copy failed four nights running and nothing said so.)
function Notify([string]$title, [string]$text) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $esc = { param($t) [Security.SecurityElement]::Escape($t) }
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$(& $esc $title)</text><text>$(& $esc $text)</text>" +
                     "</binding></visual></toast>")
        $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'    # (Windows PowerShell's own id)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
    } catch {
        Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  (no Windows notification: $($_.Exception.Message))" -Encoding ascii
    }
}
$NOTIFY = @{ backup = 'The backup'; restore_test = 'The weekly test restore'; offsite = 'The Google Drive copy'; copy = 'The network drive copy' }

# A part that fails keeps the day it started failing and how many runs in a row have failed (Settings > System turns
# red after a day of it), and says so with a notification.
function Set-Status([string]$part, [hashtable]$values) {
    $s = Read-Status
    $before = $s.$part
    if ($values.ok -eq $false) {
        $values.failing_since = if ($before -and $before.ok -eq $false -and $before.failing_since) { $before.failing_since } else { $values.at }
        $values.failures = if ($before -and $before.ok -eq $false -and $before.failures) { [int]$before.failures + 1 } else { 1 }
        if ($NOTIFY.ContainsKey($part)) {
            $runs = if ($values.failures -gt 1) { " ($($values.failures) runs in a row)" } else { '' }
            Notify "Off the Clock: $($NOTIFY[$part]) failed$runs" "$($values.message) - see Settings > System"
        }
    }
    $s | Add-Member -NotePropertyName $part -NotePropertyValue ([pscustomobject]$values) -Force
    $s | ConvertTo-Json -Depth 4 | Set-Content -Path $statusFile -Encoding ascii
}
function Remove-Status([string]$part) {
    $s = Read-Status
    if ($s.PSObject.Properties[$part]) {
        $s.PSObject.Properties.Remove($part)
        $s | ConvertTo-Json -Depth 4 | Set-Content -Path $statusFile -Encoding ascii
    }
}
function Fail($msg) {
    Log "FAILED: $msg"
    Set-Status 'backup' @{ at = $now; ok = $false; message = $msg }
    exit 1
}

$state = docker inspect --format '{{.State.Health.Status}}' $container 2>$null
if ($state -ne 'healthy') { Fail "$container is not running/healthy (state: '$state'). Is Docker Desktop running?" }

# Every table's row count (exact), for the test restore to compare with.
$countSql = "SELECT table_name || '=' || (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', " +
            "table_schema, table_name), false, true, '')))[1]::text FROM information_schema.tables " +
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
function Get-Counts([string]$db) {
    $out = @{}
    foreach ($line in (docker exec $container psql -U $DbUser -d $db -tA -c $countSql)) {
        if ($line -match '^(.+)=(\d+)$') { $out[$Matches[1]] = [int64]$Matches[2] }
    }
    return $out
}

$lastTest = (Read-Status).restore_test
$testDue = $TestRestore -or -not $lastTest -or -not $lastTest.ok -or ((Get-Date) - [datetime]$lastTest.at).TotalDays -ge 6.5
if ($testDue) { $before = Get-Counts $DbName }

docker exec $container pg_dump -U $DbUser -d $DbName -Fc -f "/tmp/$name"
if ($LASTEXITCODE -ne 0) { Fail 'pg_dump returned an error' }
$path = Join-Path $folder $name
docker cp "${container}:/tmp/$name" $path | Out-Null
if ($LASTEXITCODE -ne 0) { docker exec $container rm -f "/tmp/$name" | Out-Null; Fail 'could not copy the backup out of the container' }

# Read it back: Postgres can list what's in it, and the file here is the one it wrote.
$listing = docker exec $container pg_restore --list "/tmp/$name" 2>$null
$readable = ($LASTEXITCODE -eq 0) -and ($listing -match 'TABLE DATA public supplies')
$inside = ((docker exec $container sha256sum "/tmp/$name") -split '\s+')[0]
$here = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
if (-not $readable) { docker exec $container rm -f "/tmp/$name" | Out-Null; Fail "$name can't be read back (pg_restore --list)" }
if ($inside -ne $here) { docker exec $container rm -f "/tmp/$name" | Out-Null; Fail "$name was damaged copying it out (checksums differ)" }

$size = [math]::Round((Get-Item $path).Length / 1KB)
Log "OK: $name ($size KB, read back and checked)"
Set-Status 'backup' @{ at = $now; ok = $true; name = $name; kb = $size; message = 'read back and checked' }

# The weekly test restore: into a throwaway database, every table's rows counted against the live one.
if ($testDue) {
    $scratch = 'restore_check'
    docker exec $container psql -U $DbUser -d postgres -q -c "DROP DATABASE IF EXISTS $scratch" -c "CREATE DATABASE $scratch" 2>$null | Out-Null
    docker exec $container pg_restore -U $DbUser -d $scratch --no-owner "/tmp/$name" 2>$null
    $restored = $LASTEXITCODE -eq 0
    $after = if ($restored) { Get-Counts $scratch } else { @{} }
    docker exec $container psql -U $DbUser -d postgres -q -c "DROP DATABASE IF EXISTS $scratch" 2>$null | Out-Null
    $wrong = @()
    if ($restored) {
        $again = Get-Counts $DbName                       # (a table that changed while backing up isn't the backup's fault)
        foreach ($t in $before.Keys) {
            if ($after[$t] -ne $before[$t] -and $again[$t] -eq $before[$t]) { $wrong += "$t ($($after[$t]) of $($before[$t]))" }
        }
    }
    if (-not $restored) {
        Log "FAILED: test restore of $name - pg_restore returned an error"
        Set-Status 'restore_test' @{ at = $now; ok = $false; name = $name; message = 'pg_restore returned an error' }
    } elseif ($wrong.Count) {
        Log "FAILED: test restore of $name - rows missing: $($wrong -join ', ')"
        Set-Status 'restore_test' @{ at = $now; ok = $false; name = $name; message = "rows missing: $($wrong -join ', ')" }
    } else {
        $rows = ($after.Values | Measure-Object -Sum).Sum
        Log "OK: test restore of $name - $($after.Count) tables, $rows rows, all match"
        Set-Status 'restore_test' @{ at = $now; ok = $true; name = $name; tables = $after.Count; rows = $rows; message = 'all tables match' }
    }
}
docker exec $container rm -f "/tmp/$name" | Out-Null

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
if (-not $CopyTo) { Remove-Status 'copy' }      # (no copy elsewhere any more - the network drive was retired 2026-10-22)

# A network drive can be asleep: the modem's USB drive stopped answering the first request after a quiet spell
# (2026-10-19 to 22, "The network name cannot be found" every night at 2 am, fine by day). Asking the modem for its
# list of shares wakes it; try a few times, 20 s apart, before giving up.
function Wait-Share([string]$to) {
    if ($to -notlike '\\*') { return $true }
    $server = '\\' + ($to.TrimStart('\') -split '\\')[0]
    for ($try = 1; $try -le 4; $try++) {
        if (Test-Path $to) { return $true }
        Log "The network drive isn't answering yet - waking it (try $try of 4)"
        net view $server 2>$null | Out-Null
        Start-Sleep -Seconds 20
    }
    return (Test-Path $to)
}

if ($CopyTo) {
    try {
        if (-not (Wait-Share $CopyTo)) { throw "the network drive didn't wake up (tried for about 80 s)" }
        New-Item -ItemType Directory -Force $CopyTo | Out-Null
        try { Copy-Item $path $CopyTo -ErrorAction Stop }
        catch { Log "WARNING: the copy failed once ($($_.Exception.Message.Trim())) - trying again in 30 s"; Start-Sleep -Seconds 30; Copy-Item $path $CopyTo -ErrorAction Stop }
        $same = (Get-FileHash $path).Hash -eq (Get-FileHash (Join-Path $CopyTo $name)).Hash
        if ($same) { Log "Copied to $CopyTo (checked: identical)" } else { Log "WARNING: the copy in $CopyTo doesn't match" }
        Set-Status 'copy' @{ at = $now; ok = $same; to = $CopyTo; message = $(if ($same) { 'checked: identical' } else { "the copy doesn't match" }) }
        Get-ChildItem $CopyTo -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending |
            Select-Object -Skip $Keep | ForEach-Object { Remove-Item $_.FullName; Log "Removed old copy $($_.Name) from $CopyTo" }
        Copy-Media (Join-Path $CopyTo 'media') -Slow:($CopyTo -like '\\*')
    } catch {
        Log "WARNING: copy to $CopyTo failed: $($_.Exception.Message)"
        Set-Status 'copy' @{ at = $now; ok = $false; to = $CopyTo; message = $_.Exception.Message }
    }
}

# Off-site: encrypted, into the folder Google Drive syncs (prod only; set up with setup-offsite.ps1).
$offsiteCfg = Join-Path $env:USERPROFILE '.offtheclock\offsite.json'
$keyFile = Join-Path $env:USERPROFILE '.offtheclock\backup-key.xml'
if ($AppEnv -eq 'prod' -and (Test-Path $offsiteCfg)) {
    . "$PSScriptRoot\scripts\offsite.ps1"
    try {
        $cfg = Get-Content $offsiteCfg -Raw | ConvertFrom-Json
        if (-not (Test-Path $keyFile)) { throw 'no password set - run .\setup-offsite.ps1' }
        if (-not (Test-Path $cfg.folder)) { throw "$($cfg.folder) isn't there - is Google Drive for desktop running and signed in?" }
        $pass = Read-OffsiteKey $keyFile
        $sealed = Join-Path $env:TEMP "$name.gpg"
        Protect-Backup $path $sealed $pass
        $check = Join-Path $env:TEMP "$name.check"
        Unprotect-Backup $sealed $check $pass              # (decrypts again: what's sent is what you'd get back)
        $same = (Get-FileHash $check).Hash -eq (Get-FileHash $path).Hash
        Remove-Item $check -ErrorAction SilentlyContinue
        if (-not $same) { throw 'the encrypted copy did not decrypt to the same backup' }
        Copy-Item $sealed $cfg.folder -ErrorAction Stop
        Remove-Item $sealed
        $removed = Remove-OldOffsite $cfg.folder $OffsiteBudgetMB
        $files = Get-ChildItem $cfg.folder -Filter 'hobby_inventory_*.dump.gpg'
        $mb = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB)
        Log "OK: encrypted copy in $($cfg.folder) - $(@($files).Count) kept, $mb MB$(if ($removed) { ", $removed old removed" })"
        # ...and the videos, each sent once (2026-10-22: Drive holds the whole backup; the network drive was retired)
        $videos = Send-OffsiteMedia (Join-Path $Root 'media') $cfg.folder $pass
        Log "OK: videos on Drive - $($videos.files) files, $($videos.mb) MB$(if ($videos.sent) { ", $($videos.sent) new sent" })"
        Set-Status 'offsite' @{ at = $now; ok = $true; folder = $cfg.folder; files = @($files).Count; mb = $mb; budget_mb = $OffsiteBudgetMB
                                videos = $videos.files; videos_mb = $videos.mb; message = 'encrypted and checked' }
    } catch {
        Log "WARNING: off-site copy failed: $($_.Exception.Message)"
        Set-Status 'offsite' @{ at = $now; ok = $false; message = $_.Exception.Message }
    } finally {
        $pass = $null
        if ($sealed) { Remove-Item $sealed -ErrorAction SilentlyContinue }
    }
}

# Keep only the newest $Keep backups (older .sql backups from before this script are left alone).
Get-ChildItem $folder -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending |
    Select-Object -Skip $Keep | ForEach-Object {
        Remove-Item $_.FullName
        Log "Removed old backup $($_.Name)"
    }
