# Run the API tests and the browser tests at the same time (they use separate databases: hobby_inventory_test and
# the throwaway copies' own), then show both outputs. ~6 minutes: the API tests (~2), and the walk-through and the UI
# audit side by side on two throwaway copies (~5-6).
#
#   .\test_all.ps1            # everything (what promote.ps1 needs)
#   .\test_all.ps1 -NoAudit   # API tests + walk-through, no UI audit (quicker while working on something)
#   .\test_all.ps1 -Quick     # API tests only
#
# Each passing suite records a stamp in .tested\ (see scripts\common.ps1), so promote.ps1 can skip
# running them again on exactly the same code. Don't use the app while it runs: the walk-through
# puts the data back as it was when it started.
param([switch]$Quick, [switch]$NoAudit)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$logs = Join-Path $Root '.tested'
New-Item -ItemType Directory -Force $logs | Out-Null

function Start-Suite([string]$script, [string]$name, [string[]]$extra = @()) {
    $out = Join-Path $logs "$name.log"
    $err = Join-Path $logs "$name.err.log"
    $p = Start-Process powershell -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err `
        -ArgumentList (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Root $script)) + @($extra | Where-Object { $_ }))
    $null = $p.Handle    # PowerShell 5.1: without holding the handle now, ExitCode reads empty later
    return @{ Process = $p; Out = $out; Err = $err; Name = $name }
}

$started = Get-Date
$suites = @(Start-Suite 'run_tests.ps1' 'api')
if (-not $Quick) { $suites += Start-Suite 'run_e2e.ps1' 'e2e' @(if ($NoAudit) { '-NoAudit' }) }
Write-Host ("Running " + (($suites | ForEach-Object { $_.Name }) -join ' and ') + ' side by side...') -ForegroundColor Cyan

$failed = @()
foreach ($s in $suites) {
    $s.Process.WaitForExit()
    $code = $s.Process.ExitCode
    Write-Host ''
    Write-Host "===== $($s.Name) (exit $code) =====" -ForegroundColor Cyan
    Get-Content $s.Out | Where-Object { $_ -notmatch '^\s*\d\d_.*\.sql ok$' }
    $errors = @(Get-Content $s.Err -ErrorAction SilentlyContinue | Where-Object { $_.Trim() })
    if ($code -ne 0 -and $errors.Count) { $errors | Select-Object -Last 20 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray } }
    if ($code -ne 0) { $failed += $s.Name }
}
Write-Host ''
$took = [int]((Get-Date) - $started).TotalSeconds
if ($failed.Count) { Write-Host "FAILED: $($failed -join ', ') ($took s)" -ForegroundColor Red; exit 1 }
Write-Host "All passed in $took s." -ForegroundColor Green
exit 0
