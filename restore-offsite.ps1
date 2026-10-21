# Get an off-site backup back: decrypt a .dump.gpg from Google Drive into .\backups, ready to restore.
#
#   .\restore-offsite.ps1 -File "G:\My Drive\Off the Clock backups\hobby_inventory_20261021_020000.dump.gpg"
#   .\restore-offsite.ps1 -File <...> -SavedPassword    # use the password kept on this PC instead of typing it
#
# On a new PC: install Docker Desktop and Git for Windows, clone the app, start it (start.ps1), then run this
# and the two restore commands it prints. Without this app, any gpg does it too:
#   gpg --decrypt hobby_inventory_<when>.dump.gpg > hobby_inventory_<when>.dump
# ASCII only (Windows PowerShell 5.1).
param(
    [Parameter(Mandatory = $true)][string]$File,
    [switch]$SavedPassword
)

. "$PSScriptRoot\scripts\common.ps1"
. "$PSScriptRoot\scripts\offsite.ps1"
if (-not (Test-Path $File)) { Write-Host "No file at $File" -ForegroundColor Red; exit 1 }
$name = [IO.Path]::GetFileName($File) -replace '\.gpg$', ''
if ($name -notmatch '^hobby_inventory_\d{8}_\d{6}\.dump$') { Write-Host 'That is not one of the app''s backups.' -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force $BackupDir | Out-Null
$out = Join-Path $BackupDir $name

if ($SavedPassword) {
    $pass = Read-OffsiteKey (Join-Path $OffsiteDir 'backup-key.xml')
} else {
    $s = Read-Host 'The off-site backup password' -AsSecureString
    $pass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}
try {
    Unprotect-Backup $File $out $pass
} catch {
    Write-Host "Couldn't decrypt it: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    $pass = $null
}
Write-Host "Decrypted: $out" -ForegroundColor Green
Write-Host 'To restore it (this REPLACES the data in this copy of the app - back up first if it has anything you need):'
Write-Host "  docker cp `"$out`" ${DbContainer}:/tmp/restore.dump"
Write-Host "  docker exec $DbContainer pg_restore -U $DbUser -d $DbName --clean --if-exists /tmp/restore.dump"
