# The monthly update check (health check, 2026-10-21): what has a newer version, and any known security problems.
# Nothing is changed - it reports, and the update itself is done in dev, tested (.\test_all.ps1), then promoted.
#
#   .\check-updates.ps1          # in the dev folder; about 2 minutes (it asks PyPI, npm and Docker Hub)
#
# Looks at:
#   Python packages   api\requirements.txt: newer versions (PyPI) and pip-audit (known vulnerabilities)
#   npm packages      web\package.json: npm outdated and npm audit
#   Docker images     the exact versions pinned in the Dockerfiles: a newer patch of the same line (Docker Hub)
#   Playwright        the walk-through's browser (e2e\Dockerfile) against the newest on PyPI
# Writes backups\updates.json in both copies (dev and prod), which Settings > System reads: it turns amber after
# 40 days without a check, or while an audit finds a problem.
# ASCII only (Windows PowerShell 5.1).

. "$PSScriptRoot\scripts\common.ps1"
Set-Location $Root
$items = New-Object System.Collections.ArrayList
$auditProblems = 0
function Note($area, $name, $have, $newest, $why) {
    [void]$items.Add([pscustomobject]@{ area = $area; name = $name; have = $have; newest = $newest; note = $why })
    Write-Host ("  {0,-8} {1,-28} {2,-14} -> {3,-14} {4}" -f $area, $name, $have, $newest, $why)
}

Write-Host 'Python packages (PyPI)...' -ForegroundColor Cyan
$pyImage = (Select-String -Path api\Dockerfile -Pattern '^FROM (\S+)').Matches[0].Groups[1].Value
$pyOut = docker run --rm -v "${Root}\api:/w:ro" $pyImage sh -c "pip install -q --disable-pip-version-check -r /w/requirements.txt pip-audit >/dev/null 2>&1; pip list --outdated --format=json 2>/dev/null; echo '@@'; pip-audit -r /w/requirements.txt -f json 2>/dev/null"
$parts = ($pyOut -join "`n") -split '@@'
$pinned = @{}
foreach ($line in Get-Content api\requirements.txt) { if ($line -match '^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==([^\s#]+)') { $pinned[$Matches[1].ToLower()] = $Matches[3] } }
try {
    foreach ($p in ($parts[0] | ConvertFrom-Json)) {
        if ($pinned.ContainsKey($p.name.ToLower())) { Note 'python' $p.name $p.version $p.latest_version '' }
    }
} catch { Write-Host '  (could not read pip list)' -ForegroundColor Yellow }
try {
    $audit = $parts[1] | ConvertFrom-Json
    foreach ($d in $audit.dependencies) { foreach ($v in $d.vulns) { $auditProblems++; Note 'python' $d.name $d.version ($v.fix_versions -join ',') "SECURITY: $($v.id)" } }
} catch { Write-Host '  (could not read pip-audit)' -ForegroundColor Yellow }

Write-Host 'npm packages...' -ForegroundColor Cyan
$nodeImage = (Select-String -Path web\Dockerfile -Pattern '^FROM (\S+) AS build').Matches[0].Groups[1].Value
$npmOut = docker run --rm -v "${Root}\web:/src:ro" $nodeImage sh -c "mkdir /w && cp /src/package.json /src/package-lock.json /w/ && cd /w && npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1; npm outdated --json 2>/dev/null; echo '@@'; npm audit --json 2>/dev/null"
$parts = ($npmOut -join "`n") -split '@@'
try {
    $outdated = $parts[0] | ConvertFrom-Json
    foreach ($p in $outdated.PSObject.Properties) { Note 'npm' $p.Name $p.Value.current $p.Value.latest '' }
} catch { Write-Host '  (could not read npm outdated)' -ForegroundColor Yellow }
try {
    $audit = $parts[1] | ConvertFrom-Json
    $n = [int]$audit.metadata.vulnerabilities.total
    if ($n) { $auditProblems += $n; Note 'npm' 'npm audit' '' '' "SECURITY: $n known problem(s) - run npm audit in web\" }
} catch { Write-Host '  (could not read npm audit)' -ForegroundColor Yellow }

Write-Host 'Docker images (Docker Hub)...' -ForegroundColor Cyan
$pins = @()
foreach ($f in 'api\Dockerfile', 'web\Dockerfile', 'db\Dockerfile') {
    # python:3.13.16-slim (line 3.13, patch 16) or postgres:17.11-alpine (line 17, release 11)
    foreach ($m in (Select-String -Path $f -Pattern '^FROM ([a-z]+):(\d+(?:\.\d+)?)\.(\d+)-([a-z]+)').Matches) {
        $pins += , @($m.Groups[1].Value, $m.Groups[2].Value, [int]$m.Groups[3].Value, $m.Groups[4].Value)
    }
}
foreach ($p in $pins) {
    $repo, $line, $patch, $flavour = $p
    try {
        $url = "https://hub.docker.com/v2/repositories/library/$repo/tags?page_size=100&name=$line.&ordering=last_updated"
        $tags = (Invoke-RestMethod $url -TimeoutSec 30).results.name
        $rx = '^' + [regex]::Escape($line) + '\.(\d+)-' + $flavour + '$'
        $same = $tags | Where-Object { $_ -match $rx } | ForEach-Object { [int]([regex]::Match($_, $rx).Groups[1].Value) }
        $best = ($same | Measure-Object -Maximum).Maximum
        if ($best -gt $patch) { Note 'image' "$repo ($flavour)" "$line.$patch" "$line.$best" 'newer patch of the same line' }
        else { Write-Host "  image    $repo $line.$patch is the newest $line" }
    } catch { Write-Host "  (could not ask Docker Hub about $repo)" -ForegroundColor Yellow }
}

Write-Host 'Playwright (the walk-through)...' -ForegroundColor Cyan
try {
    $have = (Select-String -Path e2e\Dockerfile -Pattern 'playwright==([\d.]+)').Matches[0].Groups[1].Value
    $newest = (Invoke-RestMethod 'https://pypi.org/pypi/playwright/json' -TimeoutSec 30).info.version
    if ($newest -ne $have) { Note 'e2e' 'playwright' $have $newest 'its browser too: needs a walk-through run' }
} catch { Write-Host '  (could not ask PyPI about playwright)' -ForegroundColor Yellow }

# Both copies' backups folders: the API reads updates.json from there (Settings > System).
$result = [pscustomobject]@{ at = (Get-Date -Format 's'); outdated = $items.Count - @($items | Where-Object { $_.note -like 'SECURITY*' }).Count
                             audit_problems = $auditProblems; items = $items }
$json = $result | ConvertTo-Json -Depth 4
$other = if ($AppEnv -eq 'dev') { Join-Path (Split-Path $Root -Parent) 'hobby-inventory' } else { "$Root-dev" }
foreach ($dir in @($BackupDir, (Join-Path $other 'backups'))) {
    if (Test-Path (Split-Path $dir -Parent)) {
        New-Item -ItemType Directory -Force $dir | Out-Null
        Set-Content -Path (Join-Path $dir 'updates.json') -Value $json -Encoding ascii
    }
}
Write-Host ''
Write-Host ("{0} newer version(s), {1} security problem(s). Saved for Settings > System." -f $result.outdated, $auditProblems) `
    -ForegroundColor $(if ($auditProblems) { 'Red' } elseif ($result.outdated) { 'Yellow' } else { 'Green' })
