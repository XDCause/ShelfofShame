# The web code's own tests (web\src\**\*.test.js / .jsx, Vitest + jsdom): formatters, calendar helpers, Quick add,
# Stocktake... In a throwaway Node container (the same Node as the web build), in Brisbane's time zone, with a copy
# of web\ - nothing is installed on the PC or written into the project. About a minute (most of it npm ci).
#
#   .\run_web_tests.ps1          (test_all.ps1 runs it too)
# ASCII only (Windows PowerShell 5.1).

. "$PSScriptRoot\scripts\common.ps1"
$code = Get-CodeHash                  # (the code being tested: a pass is stamped for promote.ps1)
$node = (Select-String -Path (Join-Path $Root 'web\Dockerfile') -Pattern '^FROM (\S+) AS build').Matches[0].Groups[1].Value
Write-Host "Web tests ($node)..." -ForegroundColor Cyan
docker run --rm -e TZ=Australia/Brisbane -v "${Root}\web:/src:ro" $node sh -c (
    "mkdir /w && cd /src && cp -r package.json package-lock.json vite.config.js index.html src /w/ && cd /w && " +
    "npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 && npx vitest run --reporter=dot")
$result = $LASTEXITCODE
if ($result -eq 0) { Write-Host 'Web tests passed.' -ForegroundColor Green; Set-Stamp 'web' $code }
else { Write-Host 'Some web tests FAILED (see above).' -ForegroundColor Red }
exit $result
