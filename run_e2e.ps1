# Click through the whole app in a real (headless) browser - desktop and iPhone sizes.
#
#   .\run_e2e.ps1
#
# The walk-through adds, edits and deletes things, so this script:
#   1. takes a backup (backup.ps1),
#   2. runs e2e\walkthrough.py in a Playwright container on the app's Docker network,
#   3. ALWAYS restores that backup afterwards, so your data ends up exactly as it was.
# Don't use the app while it runs (~1 minute) - changes made meanwhile are undone by the restore.
# Screenshots are saved to e2e\out\ (git-ignored).

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root
$image = 'offtheclock-e2e:1.47.0'    # e2e\Dockerfile: Playwright's image with its Python package installed
$db = $DbContainer
$code = Get-CodeHash
$built = (Get-Stamp 'built')[0]

docker build -q -t $image e2e | Out-Null    # cached after the first time: instant
if ($LASTEXITCODE -ne 0) { Write-Host 'Building the walk-through image failed.' -ForegroundColor Red; exit 1 }

powershell -NoProfile -ExecutionPolicy Bypass -File .\backup.ps1
if ($LASTEXITCODE -ne 0) { Write-Host 'Backup failed - not running the walk-through.' -ForegroundColor Red; exit 1 }
$restorePoint = Get-ChildItem backups -Filter 'hobby_inventory_*.dump' | Sort-Object Name -Descending | Select-Object -First 1
Write-Host "Restore point: $($restorePoint.Name)" -ForegroundColor Cyan

New-Item -ItemType Directory -Force e2e\out | Out-Null
Remove-Item e2e\out\*.png -ErrorAction SilentlyContinue
try {
    docker run --rm --network $Network --ipc=host `
        -v "${PSScriptRoot}\e2e:/e2e" -v "${PSScriptRoot}\e2e\out:/out" $image `
        python /e2e/walkthrough.py
    $result = $LASTEXITCODE
} finally {
    Write-Host 'Restoring your data...' -ForegroundColor Cyan
    docker cp $restorePoint.FullName "${db}:/tmp/restore.dump" | Out-Null
    docker exec -e 'PGOPTIONS=-c client_min_messages=warning' $db pg_restore -U $DbUser -d $DbName --clean --if-exists /tmp/restore.dump
    if ($LASTEXITCODE -eq 0) { Write-Host 'Data restored.' -ForegroundColor Green }
    else { Write-Host "RESTORE FAILED - restore $($restorePoint.Name) by hand (see README)." -ForegroundColor Red }
    docker exec $db rm -f /tmp/restore.dump | Out-Null
}
# A pass counts for promote.ps1 only if the running app was built from the code on disk.
if ($result -eq 0) {
    if ($built -eq $code) { Set-Stamp 'e2e' $code }
    else { Write-Host 'Note: the running app was built from older code than is on disk (rebuild with .\dev.ps1), so this pass is not recorded for promote.ps1.' -ForegroundColor Yellow }
}
exit $result
