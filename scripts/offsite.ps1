# The off-site copy's pieces, shared by backup.ps1, setup-offsite.ps1 and restore-offsite.ps1 (dot-source it).
#
# Encryption: gpg (it comes with Git for Windows), symmetric AES-256 with your password - a standard format, so
# any gpg anywhere opens it:  gpg --decrypt hobby_inventory_<when>.dump.gpg > hobby_inventory_<when>.dump
# The password is kept on this PC with Windows' own protection (DPAPI: only your Windows account on this PC can
# read it), so the 2 am backup can use it. Keep the password somewhere else too (a password manager): if this PC
# is lost, it's the only way to open the copies on Google Drive.
# ASCII only (Windows PowerShell 5.1).

$OffsiteDir = Join-Path $env:USERPROFILE '.offtheclock'
$GnupgHome = Join-Path $OffsiteDir 'gnupg'      # gpg's own settings folder for this (never your own keyring)

function Find-Gpg {
    foreach ($p in @("$env:ProgramFiles\Git\usr\bin\gpg.exe", "${env:ProgramFiles(x86)}\GnuPG\bin\gpg.exe", "$env:ProgramFiles\GnuPG\bin\gpg.exe")) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    $g = Get-Command gpg -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    throw 'gpg not found (it comes with Git for Windows)'
}

function Read-OffsiteKey([string]$file) {
    $secure = Import-Clixml $file
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

# gpg reads the password from its standard input (never the command line, where other programs could see it).
# Git's gpg is an MSYS program: it wants /c/Users/... rather than C:\Users\... (a Windows gpg takes either).
function ConvertTo-GpgPath([string]$path, [string]$gpg) {
    if ($gpg -notlike '*\Git\usr\bin\*') { return $path }
    $full = [IO.Path]::GetFullPath($path)
    return '/' + $full.Substring(0, 1).ToLower() + $full.Substring(2).Replace('\', '/')
}

function Invoke-Gpg([string]$pass, [string[]]$gpgArgs) {
    New-Item -ItemType Directory -Force $GnupgHome | Out-Null
    $gpg = Find-Gpg
    $env:GNUPGHOME = ConvertTo-GpgPath $GnupgHome $gpg
    $savedEncoding = $OutputEncoding
    $savedErrors = $ErrorActionPreference
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)   # (5.1 pipes ASCII by default: a password with an e-acute would change)
    $ErrorActionPreference = 'Continue'                              # (gpg's notes on stderr aren't errors; its exit code says)
    try {
        $gpgArgs = $gpgArgs | ForEach-Object { if ($_ -match '^[A-Za-z]:\\') { ConvertTo-GpgPath $_ $gpg } else { $_ } }
        $pass | & $gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-fd 0 @gpgArgs 2>$null | Out-Null
        $code = $LASTEXITCODE
    } finally {
        $OutputEncoding = $savedEncoding
        $ErrorActionPreference = $savedErrors
    }
    if ($code -ne 0) { throw "gpg failed ($code) - a wrong password?" }
}

function Protect-Backup([string]$from, [string]$to, [string]$pass) {
    Invoke-Gpg $pass @('--symmetric', '--cipher-algo', 'AES256', '--s2k-mode', '3', '--s2k-digest-algo', 'SHA512',
                       '--s2k-count', '65011712', '--compress-algo', 'none', '--output', $to, $from)
}

function Unprotect-Backup([string]$from, [string]$to, [string]$pass) {
    Invoke-Gpg $pass @('--decrypt', '--output', $to, $from)
}

# Keep: the newest backup of each of the last 7 days, then one a week for 4 more weeks, then one a month for 6
# months; and never more than $budgetMB in all (the oldest go first, always keeping 3). Answers how many went.
function Remove-OldOffsite([string]$folder, [int]$budgetMB) {
    $files = @(Get-ChildItem $folder -Filter 'hobby_inventory_*.dump.gpg' | Sort-Object Name -Descending)
    $cal = [Globalization.CultureInfo]::InvariantCulture.Calendar
    $days = @{}; $weeks = @{}; $months = @{}; $keep = @{}
    $moreWeeks = 0; $moreMonths = 0                  # (weeks and months beyond the ones the newer copies already cover)
    foreach ($f in $files) {
        $d = [datetime]::ParseExact($f.Name.Substring(16, 8), 'yyyyMMdd', $null)
        $day = $d.ToString('yyyyMMdd'); $month = $d.ToString('yyyyMM')
        $week = '{0}-{1}' -f $d.Year, $cal.GetWeekOfYear($d, [Globalization.CalendarWeekRule]::FirstFourDayWeek, [DayOfWeek]::Monday)
        $take = $false
        if ($days.Count -lt 7) { $take = -not $days.ContainsKey($day) }
        elseif ($moreWeeks -lt 4) { if (-not $weeks.ContainsKey($week)) { $take = $true; $moreWeeks++ } }
        elseif ($moreMonths -lt 6) { if (-not $months.ContainsKey($month)) { $take = $true; $moreMonths++ } }
        if ($take) { $keep[$f.Name] = $true; $days[$day] = $true; $weeks[$week] = $true; $months[$month] = $true }
    }
    $removed = 0
    foreach ($f in $files) { if (-not $keep.ContainsKey($f.Name)) { Remove-Item $f.FullName; $removed++ } }
    $left = @(Get-ChildItem $folder -Filter 'hobby_inventory_*.dump.gpg' | Sort-Object Name)
    while ($left.Count -gt 3 -and (($left | Measure-Object Length -Sum).Sum / 1MB) -gt $budgetMB) {
        Remove-Item $left[0].FullName; $removed++
        $left = @($left | Select-Object -Skip 1)
    }
    return $removed
}
