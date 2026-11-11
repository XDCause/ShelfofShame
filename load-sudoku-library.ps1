# Load the sudoku library (the Hardest 100 and the weekly's puzzles) into this copy's database, from
# data\sudoku\hardest-published.tsv - the sudoku community's hardest puzzles, which are NOT ours to publish, so the
# file is kept out of the public repo (data\ is git-ignored) and copied between the PCs by hand.
#
#   .\load-sudoku-library.ps1                          # this copy (prod or dev: from .env)
#   .\load-sudoku-library.ps1 -Container hobby-e2e-db  # another copy's database (run_e2e.ps1's throwaway copy)
#   .\load-sudoku-library.ps1 -File other.tsv -List app-search   # another list (e.g. the desktop search's finds)
#
# Safe to run again: the list is replaced. Without it the app falls back to its own lists (web/src/modules/sudoku).
param([string]$Container, [string]$File = 'data\sudoku\hardest-published.tsv', [string]$List = 'hardest')

. "$PSScriptRoot\scripts\common.ps1"
if ($Container) { $DbContainer = $Container }
Set-Location -Path $Root

if (-not (Test-Path $File)) {
    Write-Host "No $File here - nothing to load (the app uses its own lists)." -ForegroundColor Yellow
    exit 0
}
if ($List -notmatch '^[a-z0-9-]{2,40}$') { Write-Host "A list name is lower-case letters, digits and dashes." -ForegroundColor Red; exit 1 }

$rows = @()
foreach ($line in Get-Content $File) {
    if ($line -match '^(\d+)\t(\d+)\t(\d+)\t([0-9]{81})\s*$') {
        $rows += "('$List', $($Matches[1]), '$($Matches[4])', $($Matches[2]))"
    }
}
if ($rows.Count -eq 0) { Write-Host "No puzzles found in $File." -ForegroundColor Red; exit 1 }

$sql = "BEGIN;`nDELETE FROM sudoku_library WHERE list_key = '$List';`n" +
       "INSERT INTO sudoku_library (list_key, rank, puzzle, measure) VALUES`n" + ($rows -join ",`n") + ";`nCOMMIT;`n"
$sql | docker exec -i $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Loading failed (has the database had db\init\93_sudoku.sql? Run .\migrate.ps1)." -ForegroundColor Red; exit 1 }
Write-Host "Loaded $($rows.Count) puzzles into the '$List' list ($DbContainer)." -ForegroundColor Green
