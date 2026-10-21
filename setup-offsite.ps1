# Set up the off-site backup: an encrypted copy of each nightly backup in your Google Drive.
#
#   .\setup-offsite.ps1                       # asks for the folder and a password, then tests it
#   .\setup-offsite.ps1 -Folder "G:\My Drive\Off the Clock backups"
#   .\setup-offsite.ps1 -Off                  # stop sending copies (the ones on Drive stay)
#
# Before you start: install Google Drive for desktop (google.com/drive/download) and sign in. It shows your
# Drive as a drive letter (usually G:) and uploads whatever is put in it.
#
# The password: YOU choose it (12 characters or more). It's kept on this PC so the 2 am backup can use it,
# protected by Windows so only your account on this PC can read it. Put it in a password manager as well:
# if this PC is lost, it's the only way to open the copies on Drive. Nobody - not Google, not the app - can
# open them without it.
# ASCII only (Windows PowerShell 5.1).
param(
    [string]$Folder = '',
    [switch]$Off
)

. "$PSScriptRoot\scripts\common.ps1"
. "$PSScriptRoot\scripts\offsite.ps1"
$cfgFile = Join-Path $OffsiteDir 'offsite.json'
$keyFile = Join-Path $OffsiteDir 'backup-key.xml'
New-Item -ItemType Directory -Force $OffsiteDir | Out-Null

if ($Off) {
    Remove-Item $cfgFile -ErrorAction SilentlyContinue
    Write-Host 'Off-site copies stopped. The copies already on Drive are left there; the password is kept (delete'
    Write-Host "$keyFile yourself if you want it gone)."
    exit 0
}
if ($AppEnv -ne 'prod') { Write-Host 'Run this in the prod folder (only prod sends copies off-site).' -ForegroundColor Yellow; exit 1 }
try { Find-Gpg | Out-Null } catch { Write-Host 'gpg was not found - install Git for Windows (it comes with gpg).' -ForegroundColor Red; exit 1 }

# The folder: given, or found (Google Drive for desktop's "My Drive" on any drive letter).
if (-not $Folder) {
    $drive = Get-PSDrive -PSProvider FileSystem | ForEach-Object { Join-Path $_.Root 'My Drive' } | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $drive) {
        Write-Host "Google Drive for desktop isn't showing a 'My Drive' folder. Install it and sign in, or give -Folder." -ForegroundColor Yellow
        exit 1
    }
    $Folder = Join-Path $drive 'Off the Clock backups'
    $answer = Read-Host "Put the encrypted copies in '$Folder'? (Enter = yes, or type another folder)"
    if ($answer) { $Folder = $answer }
}
New-Item -ItemType Directory -Force $Folder | Out-Null

# The password (asked twice; never shown, never written anywhere but the protected file).
if ((Test-Path $keyFile) -and ((Read-Host 'A password is already set. Keep it? (Enter = yes, n = choose a new one)') -ne 'n')) {
    $pass = Read-OffsiteKey $keyFile
} else {
    while ($true) {
        $a = Read-Host 'Choose a password for the off-site copies (12+ characters)' -AsSecureString
        $b = Read-Host 'Type it again' -AsSecureString
        $pa = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($a))
        $pb = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($b))
        if ($pa -ne $pb) { Write-Host "They don't match - again." -ForegroundColor Yellow; continue }
        if ($pa.Length -lt 12) { Write-Host 'At least 12 characters, please.' -ForegroundColor Yellow; continue }
        $a | Export-Clixml $keyFile          # (Windows DPAPI: only this account on this PC can read it back)
        $pass = $pa
        $pa = $pb = $null
        break
    }
}

# Test it now: encrypt the newest backup, decrypt it again, compare.
$newest = Get-ChildItem $BackupDir -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending | Select-Object -First 1
if ($newest) {
    $sealed = Join-Path $env:TEMP "$($newest.Name).gpg"; $back = Join-Path $env:TEMP "$($newest.Name).check"
    try {
        Protect-Backup $newest.FullName $sealed $pass
        Unprotect-Backup $sealed $back $pass
        if ((Get-FileHash $back).Hash -ne (Get-FileHash $newest.FullName).Hash) { throw 'the test copy did not decrypt to the same file' }
        Copy-Item $sealed $Folder
        Write-Host "Test copy OK: $($newest.Name).gpg is in $Folder" -ForegroundColor Green
    } catch {
        Write-Host "The test failed: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    } finally {
        Remove-Item $sealed, $back -ErrorAction SilentlyContinue
    }
}
$pass = $null
@{ folder = $Folder; set_up = (Get-Date -Format 's') } | ConvertTo-Json | Set-Content $cfgFile -Encoding ascii
Write-Host ''
Write-Host 'Done. Each nightly backup now also goes to Google Drive, encrypted.' -ForegroundColor Green
Write-Host 'Now put the password in your password manager - without it the copies on Drive cannot be opened.'
Write-Host 'To get a copy back on any PC: .\restore-offsite.ps1 -File "<the .gpg file>" (or gpg --decrypt).'
