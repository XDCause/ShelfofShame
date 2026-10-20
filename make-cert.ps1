# The app's HTTPS certificate (scripts\make_cert.py does the work, inside the API image).
#
#   .\make-cert.ps1           # make it if it's missing, out of date, or this PC's names / addresses changed
#   .\make-cert.ps1 -Force    # make a new one anyway
#
# The first time, it also makes "Off the Clock local CA" in %USERPROFILE%\.offtheclock\ca (shared by dev and prod).
# Install that CA once on each phone / PC (README: "HTTPS on your devices"); after that the app opens with no
# warnings, at https://<this PC's name>.local:<port>, and passkeys work. dev.ps1 and promote.ps1 run this.
# ASCII only (Windows PowerShell 5.1).
param([switch]$Force)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root

$caDir = Join-Path $env:USERPROFILE '.offtheclock\ca'
New-Item -ItemType Directory -Force $caDir, (Join-Path $Root 'certs') | Out-Null

# Every name and address the app is reached by: the PC's name (and name.local), its own addresses (Wi-Fi, Tailscale...)
$names = @($env:COMPUTERNAME.ToLower())
$ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { $_.IPAddress })
$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if ($tailscale) {
    try {
        $ts = (& $tailscale.Source status --json 2>$null) -join "`n" | ConvertFrom-Json
        if ($ts.Self.DNSName) { $names += $ts.Self.DNSName.TrimEnd('.').ToLower() }
    } catch { }
}

$image = "$Prefix-api:1.0"
if (-not (docker image inspect $image 2>$null)) {
    Write-Host "Building the API image first (it makes the certificate)..." -ForegroundColor Cyan
    docker compose build api 2>$null | Out-Null
}
$args2 = @()
foreach ($n in $names) { $args2 += @('--name', $n) }
foreach ($i in $ips) { $args2 += @('--ip', $i) }
if ($Force) { $args2 += '--force' }
docker run --rm -v "${caDir}:/ca" -v "${Root}\certs:/certs" -v "${Root}\scripts:/scripts:ro" $image `
    python /scripts/make_cert.py @args2
if ($LASTEXITCODE -ne 0) { Write-Host 'Making the certificate failed.' -ForegroundColor Red; exit 1 }
