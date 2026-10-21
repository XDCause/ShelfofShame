# Get an off-site backup back from Google Drive: a database backup (.dump.gpg, into .\backups, ready to restore) or
# the videos (media\*.gpg, into .\media).
#
#   .\restore-offsite.ps1 -File "G:\My Drive\Off the Clock backups\hobby_inventory_20261021_020000.dump.gpg"
#   .\restore-offsite.ps1 -Videos "G:\My Drive\Off the Clock backups"     # every video (ones already here are skipped)
#   ... -SavedPassword                    # use the password kept on this PC instead of typing it
#
# On a new PC: install Docker Desktop and Git for Windows, clone the app, start it (start.ps1), then run this
# (the newest backup, then -Videos) and the two restore commands it prints. Without this app, any gpg does it too:
#   gpg --decrypt hobby_inventory_<when>.dump.gpg > hobby_inventory_<when>.dump
# ASCII only (Windows PowerShell 5.1).
param(
    [string]$File = '',
    [string]$Videos = '',
    [switch]$SavedPassword
)

. "$PSScriptRoot\scripts\common.ps1"
. "$PSScriptRoot\scripts\offsite.ps1"
if (-not $File -and -not $Videos) { Write-Host 'Give -File <a .dump.gpg> or -Videos <the Drive folder>.' -ForegroundColor Yellow; exit 1 }
if ($File -and -not (Test-Path $File)) { Write-Host "No file at $File" -ForegroundColor Red; exit 1 }
if ($Videos -and -not (Test-Path (Join-Path $Videos 'media'))) { Write-Host "No media folder in $Videos" -ForegroundColor Red; exit 1 }
if ($File) {
    $name = [IO.Path]::GetFileName($File) -replace '\.gpg$', ''
    if ($name -notmatch '^hobby_inventory_\d{8}_\d{6}\.dump$') { Write-Host 'That is not one of the app''s backups.' -ForegroundColor Red; exit 1 }
}

if ($SavedPassword) {
    $pass = Read-OffsiteKey (Join-Path $OffsiteDir 'backup-key.xml')
} else {
    $s = Read-Host 'The off-site backup password' -AsSecureString
    $pass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}
try {
    if ($File) {
        New-Item -ItemType Directory -Force $BackupDir | Out-Null
        $out = Join-Path $BackupDir $name
        Unprotect-Backup $File $out $pass
        Write-Host "Decrypted: $out" -ForegroundColor Green
        Write-Host 'To restore it (this REPLACES the data in this copy of the app - back up first if it has anything you need):'
        Write-Host "  docker cp `"$out`" ${DbContainer}:/tmp/restore.dump"
        Write-Host "  docker exec $DbContainer pg_restore -U $DbUser -d $DbName --clean --if-exists /tmp/restore.dump"
    }
    if ($Videos) {
        $from = Join-Path $Videos 'media'
        $media = Join-Path $Root 'media'
        $got = 0
        foreach ($f in Get-ChildItem $from -Recurse -File -Filter '*.gpg') {
            $rel = $f.FullName.Substring($from.TrimEnd('\').Length + 1) -replace '\.gpg$', ''
            $to = Join-Path $media $rel
            if (Test-Path $to) { continue }
            New-Item -ItemType Directory -Force (Split-Path $to -Parent) | Out-Null
            Unprotect-Backup $f.FullName $to $pass
            $got++
        }
        Write-Host "Videos: $got brought back into $media (ones already there were left alone)." -ForegroundColor Green
    }
} catch {
    Write-Host "Couldn't decrypt it: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    $pass = $null
}
