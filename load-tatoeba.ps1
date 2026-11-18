# Load real example sentences from Tatoeba (tatoeba.org, CC BY 2.0 FR) into this copy's database, for Language
# learning > Read: Spanish sentences with their English translations (lang_sentences, db\init\A11_language_sentences.sql).
#
#   .\load-tatoeba.ps1                          # this copy (prod or dev: from .env)
#   .\load-tatoeba.ps1 -Container hobby-e2e-db  # another copy's database
#   .\load-tatoeba.ps1 -Refresh                 # download Tatoeba's files again (they're re-exported weekly)
#
# A one-time download a person starts, not a live source: three files from https://downloads.tatoeba.org/exports/
# per_language/ (about 33 MB, one request each) are kept in data\tatoeba (git-ignored: data\ is never in the repo)
# and not downloaded again unless -Refresh. scripts\tatoeba_filter.py (run in a throwaway container from this copy's
# API image, no network) keeps the Spanish sentences of 3-20 words that have an English translation, and the result
# replaces the course's sentences. What you've read stays (Tatoeba's ids don't change). No usernames, no audio.
# ASCII only (Windows PowerShell 5.1).
param([string]$Container, [switch]$Refresh, [int]$MinWords = 3, [int]$MaxWords = 20)

. "$PSScriptRoot\scripts\common.ps1"
if ($Container) { $DbContainer = $Container }
Set-Location -Path $Root

$Lang = 'spa'      # Tatoeba's code for the language
$Course = 'es'     # the app's (lang_languages.course)
$Dir = Join-Path $Root 'data\tatoeba'
$Base = 'https://downloads.tatoeba.org/exports/per_language'
$Files = @(
    @{ Name = "${Lang}_sentences.tsv.bz2"; Url = "$Base/$Lang/${Lang}_sentences.tsv.bz2" },
    @{ Name = 'eng_sentences.tsv.bz2'; Url = "$Base/eng/eng_sentences.tsv.bz2" },
    @{ Name = "$Lang-eng_links.tsv.bz2"; Url = "$Base/$Lang/$Lang-eng_links.tsv.bz2" }
)

New-Item -ItemType Directory -Force -Path $Dir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'   # (5.1's progress bar makes big downloads crawl)
foreach ($f in $Files) {
    $path = Join-Path $Dir $f.Name
    if ((Test-Path $path) -and -not $Refresh) { Write-Host "Have $($f.Name) (-Refresh to download it again)."; continue }
    Write-Host "Downloading $($f.Url) ..."
    try {
        Invoke-WebRequest -Uri $f.Url -OutFile "$path.part" -UseBasicParsing -UserAgent 'OffTheClock-personal/1.0 (one-time download)'
        Move-Item -Force "$path.part" $path
    } catch {
        Remove-Item -ErrorAction SilentlyContinue "$path.part"
        Write-Host "Couldn't download $($f.Name): $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# Filter in a throwaway container from this copy's API image (Python 3.13; bz2 is built in), with no network.
$image = docker inspect --format '{{.Config.Image}}' $ApiContainer 2>$null
if ($LASTEXITCODE -eq 0 -and $image) { docker image inspect $image 2>$null | Out-Null }
if ($LASTEXITCODE -ne 0 -or -not $image) { $image = 'python:3.13-slim' }
Write-Host "Picking the sentences ..."
docker run --rm --network none --entrypoint python `
    -v "${Dir}:/data" -v "$Root\api\app:/code:ro" -v "$Root\scripts:/scripts:ro" `
    $image -I /scripts/tatoeba_filter.py /data /code $Lang $Course $MinWords $MaxWords
if ($LASTEXITCODE -ne 0) { Write-Host "Picking the sentences failed." -ForegroundColor Red; exit 1 }
$tsv = Join-Path $Dir "$Course-en.tsv"

# Into the database: A11's tables first (idempotent - a copy that hasn't had migrate.ps1 yet), then the sentences.
# Files go in with docker cp (never through a PowerShell pipe: 5.1 would re-encode the accents).
docker cp "$Root\db\init\A11_language_sentences.sql" "${DbContainer}:/tmp/A11_language_sentences.sql" | Out-Null
docker cp $tsv "${DbContainer}:/tmp/tatoeba.tsv" | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Couldn't copy into $DbContainer (is it running?)." -ForegroundColor Red; exit 1 }
docker exec $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 -f /tmp/A11_language_sentences.sql | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Couldn't set up the sentence tables (has the database had A09 / A10? Run .\migrate.ps1)." -ForegroundColor Red; exit 1 }
$load = @"
BEGIN;
DELETE FROM lang_sentences WHERE course = '$Course';
\copy lang_sentences (sentence_id, course, text, english, words, word_count, rarity) FROM '/tmp/tatoeba.tsv'
INSERT INTO lang_sentence_words (course, word, sentence_id)
    SELECT DISTINCT course, unnest(words), sentence_id FROM lang_sentences WHERE course = '$Course';
COMMIT;
ANALYZE lang_sentences;
ANALYZE lang_sentence_words;
"@
$load | docker exec -i $DbContainer psql -U $DbUser -d $DbName -q -v ON_ERROR_STOP=1 | Out-Null
$ok = $LASTEXITCODE -eq 0
docker exec $DbContainer rm -f /tmp/tatoeba.tsv /tmp/A11_language_sentences.sql | Out-Null
if (-not $ok) { Write-Host "Loading failed." -ForegroundColor Red; exit 1 }
$n = docker exec $DbContainer psql -U $DbUser -d $DbName -tA -c "SELECT count(*) FROM lang_sentences WHERE course = '$Course'"
Write-Host "Loaded $n Spanish sentences with English translations ($DbContainer). Sentences from Tatoeba (tatoeba.org), CC BY 2.0 FR." -ForegroundColor Green
