# The showcase: how the app has looked over time, for showing people. Screenshots of the same pages from each big
# step of the look (and today), all with the same MADE-UP sample data - nothing of yours is in them.
#
#   .\showcase.ps1                 # every version below, then showcase\index.html (~15-20 minutes the first time)
#   .\showcase.ps1 -Only now       # just today's (after a big update: re-makes that column, keeps the rest)
#   .\showcase.ps1 -Only v6,now    # some of them
#
# Open showcase\index.html in a browser: pick a version, a page, laptop or phone, or compare two side by side.
# showcase\ is git-ignored (pictures don't go in the public repo), so zip it up to send it to someone.
#
# How: a throwaway copy of the app (hobby-showcase-*, from the images .\dev.ps1 built) starts EMPTY - not a copy of
# your data - and e2e\sample_data.py fills it through the API (an invented "Alex": kits, games, hikes, a trip...).
# Each version's web pages are built from git (prod's build: no unfinished hobbies) and served by a small nginx in
# front of that same API, then e2e\showcase.py takes the pictures. Old pages against today's API mostly look as they
# did; the odd number may be missing where the API has changed since. The copy and its volume are deleted at the end.
# ASCII only (Windows PowerShell 5.1).
param([string[]]$Only)

. "$PSScriptRoot\scripts\common.ps1"
Set-Location -Path $Root

# The big steps in the look (prod commits). Add a line here after the next big UI change.
$versions = @(
    @{ Key = 'v1'; Sha = 'ab5819f'; Date = '13 Oct 2026'; Title = 'Shelf of Shame'; Note = 'Where it started: the model-kit supplies inventory - paints, kits, time tracking, an Apple-style look.' }
    @{ Key = 'v2'; Sha = 'f8bb0a3'; Date = '13 Oct 2026'; Title = 'Off the Clock'; Note = 'A hobby hub: Home, and a module for each hobby.'; Paths = 'supplies=/models/inventory' }
    @{ Key = 'v3'; Sha = '1084ee5'; Date = '13 Oct 2026'; Title = 'Navy'; Note = 'A more creative look: navy dark theme, a hero on Home, recent activity, search.'; Paths = 'supplies=/models/inventory' }
    @{ Key = 'v4'; Sha = '0f5a5f4'; Date = '15 Oct 2026'; Title = 'Hobby cards'; Note = 'More hobbies, each with its numbers in its own card on Home; friendly empty pages.' }
    @{ Key = 'v5'; Sha = '659f11f'; Date = '20 Oct 2026'; Title = 'Every hobby'; Note = 'Hiking, gardening, precision shooting and travel built - the last of the first look.' }
    @{ Key = 'v6'; Sha = '073c3b5'; Date = '20 Oct 2026'; Title = 'Dusk Grove'; Note = 'The look rebuilt: forest-night and linen colours, light and grain, each hobby its own colour.' }
    @{ Key = 'v7'; Sha = '1e84a63'; Date = '20 Oct 2026'; Title = 'Botanical editorial'; Note = 'Redesigned: a banner on every page, Playfair + Inter, a pine sidebar, the journal as paper.' }
    @{ Key = 'now'; Sha = 'HEAD'; Date = (Get-Date -Format 'd MMM yyyy'); Title = 'Today'; Note = 'The latest: a to-do list, a tidier Home, banners with their own time of day.' }
)
if ($Only) { $todo = @($versions | Where-Object { $Only -contains $_.Key }) } else { $todo = $versions }
if (-not $todo) { Write-Host "No version called $($Only -join ', '). Choose from: $(($versions | ForEach-Object { $_.Key }) -join ', ')" -ForegroundColor Red; exit 1 }

$image = 'offtheclock-e2e:1.47.0'
$work = Join-Path $Root '.showcase'
$out = Join-Path $Root 'showcase'
$c = @{ Name = 'hobby-showcase'; Volume = 'hobby_showcase_pgdata'; Db = '5438'; Api = '8005'; Web = '8085'; Https = '8448' }
$net = "$($c.Name)_default"
$server = "$($c.Name)-pages"

function In-Copy([scriptblock]$block) {
    $vars = @{
        APP_PREFIX = $c.Name; DB_VOLUME = $c.Volume; POSTGRES_PORT = $c.Db; API_PORT = $c.Api; WEB_PORT = $c.Web; WEB_HTTPS_PORT = $c.Https
        MEDIA_PATH = './.showcase/media'; BACKUP_PATH = './.showcase/backups'; DAILY_SYNCS = 'off'
        APP_ENV = 'prod'     # as prod looked: no DEV badge (old versions ask the API which copy it is)
        OUTSIDE_SITES = 'stand-ins'
    }
    foreach ($k in $vars.Keys) { Set-Item "Env:$k" $vars[$k] }
    try { & $block } finally { foreach ($k in $vars.Keys) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } }
}
function Remove-Copy {
    docker rm -f $server 2>$null | Out-Null
    In-Copy { docker compose -p $c.Name down -v --remove-orphans 2>$null | Out-Null }
    foreach ($s in 'db', 'api', 'web') { docker rmi "$($c.Name)-${s}:1.0" 2>$null | Out-Null }
}
# Safety: `down -v` deletes a volume, so make sure compose really means the throwaway one.
$cfg = (In-Copy { docker compose -p $c.Name config --format json 2>$null }) -join "`n" | ConvertFrom-Json
$vols = @($cfg.volumes.PSObject.Properties | ForEach-Object { $_.Value.name })
if ($cfg.name -ne $c.Name -or $vols.Count -ne 1 -or $vols[0] -ne $c.Volume) {
    Write-Host "Refusing to go on: compose resolved to project '$($cfg.name)', volumes '$($vols -join ', ')'." -ForegroundColor Red
    exit 1
}

# Which pages a version had: one at its own address (Paths), a hobby's module folder (and not still under construction),
# or a page's address in the code.
function Test-Page([string]$sha, [string]$key, [string]$paths) {
    if ($key -eq 'home' -or ";$paths" -match ";$key=") { return $true }
    $folder = @{ shooting = 'shooting'; models = 'models'; boardgames = 'boardgames'; volleyball = 'volleyball'; videogames = 'videogames'
        chess = 'chess'; reading = 'reading'; hiking = 'hiking'; gardening = 'gardening'; travel = 'travel' }[$key]
    if ($folder) {
        git cat-file -e "${sha}:web/src/modules/$folder/manifest.jsx" 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        return -not ((git show "${sha}:web/src/modules/$folder/manifest.jsx") -match 'underConstruction:\s*true')
    }
    # (the page's address in quotes, e.g. path="/goals" - not api.js, where the same words are the API's addresses;
    # [[:punct:]] for the quotes because Windows PowerShell 5.1 mangles a " passed to git)
    git grep -q -E ('[[:punct:]]/' + $key + '[[:punct:]]') $sha -- web/src ':!web/src/api.js' 2>$null
    return $LASTEXITCODE -eq 0
}
$pageKeys = 'home', 'supplies', 'models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'hiking', 'gardening',
    'shooting', 'travel', 'goals', 'journal', 'calendar'

docker build -q -t $image e2e | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'Building the browser image failed.' -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Force $out, "$work\media", "$work\backups", "$work\dist" | Out-Null
Remove-Copy
# The pages' own little server: https on the app's certificate, /api/ to the copy's API.
@'
server {
    listen 443 ssl;
    ssl_certificate /certs/server.crt;
    ssl_certificate_key /certs/server.key;
    root /html;
    location / { try_files $uri /index.html; }
    location /api/ { proxy_pass http://api:8000; proxy_set_header Host $host; client_max_body_size 50m; }
}
'@ | Set-Content -Encoding ascii "$work\pages.conf"

$result = 1
try {
    # 1. The empty copy, filled with the sample data.
    Write-Host 'Starting an empty copy and filling it with sample data...' -ForegroundColor Cyan
    foreach ($s in 'db', 'api', 'web') { docker tag "$Prefix-${s}:1.0" "$($c.Name)-${s}:1.0" }
    In-Copy { docker compose -p $c.Name up -d --no-build 2>$null | Out-Null }
    if (-not (Wait-Healthy @("$($c.Name)-db", "$($c.Name)-api", "$($c.Name)-web"))) { throw 'The showcase copy did not start.' }
    $password = 'showcase ' + [guid]::NewGuid().ToString('N')
    $password | docker exec -i "$($c.Name)-api" python -m app.auth set-password --stdin --reset-authenticator --sign-out-everywhere | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Setting the copy''s password failed.' }
    docker run --rm --network $net -e "E2E_PASSWORD=$password" -e 'BASE=https://web' -v "${Root}\e2e:/e2e" $image python /e2e/sample_data.py
    if ($LASTEXITCODE -ne 0) { throw 'Filling in the sample data failed.' }

    # 2. Each version: its pages built from git, served, photographed.
    foreach ($v in $todo) {
        $sha = (git rev-parse --short $v.Sha).Trim()
        Write-Host "$($v.Key) $($v.Title) ($sha): building its pages..." -ForegroundColor Cyan
        $src = Join-Path $work "src-$($v.Key)"
        git worktree remove --force $src 2>$null | Out-Null
        git worktree add --detach $src $sha 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Couldn't check out $sha." }
        try {
            docker build -q --target build --build-arg APP_ENV=prod -t "showcase-build:$($v.Key)" "$src\web" | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Building $($v.Key)'s pages failed." }
        } finally { git worktree remove --force $src 2>$null | Out-Null }
        $dist = Join-Path $work "dist\$($v.Key)"
        Remove-Item $dist -Recurse -Force -ErrorAction SilentlyContinue
        $tmp = docker create "showcase-build:$($v.Key)"
        docker cp "${tmp}:/app/dist" $dist | Out-Null
        docker rm $tmp | Out-Null
        docker rmi "showcase-build:$($v.Key)" 2>$null | Out-Null

        docker rm -f $server 2>$null | Out-Null
        docker run -d --name $server --network $net --network-alias pages -v "${dist}:/html:ro" `
            -v "${work}\pages.conf:/etc/nginx/conf.d/default.conf:ro" -v "${Root}\certs:/certs:ro" nginx:1.27-alpine | Out-Null
        Start-Sleep 2
        Remove-Item "$out\$($v.Key)" -Recurse -Force -ErrorAction SilentlyContinue
        docker run --rm --network $net --ipc=host -e "E2E_PASSWORD=$password" -e 'API_BASE=https://web' -e "PATHS=$($v.Paths)" `
            -v "${Root}\e2e:/e2e" -v "${out}:/out" $image python /e2e/showcase.py https://pages $v.Key | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Taking $($v.Key)'s pictures failed." }
        docker rm -f $server 2>$null | Out-Null
        Write-Host "  done" -ForegroundColor DarkGray
    }

    # 3. The gallery: what each version had, and index.html to look through them.
    $list = foreach ($v in $versions) {
        $sha = (git rev-parse --short $v.Sha).Trim()
        [pscustomobject]@{ key = $v.Key; sha = $sha; date = $v.Date; title = $v.Title; note = $v.Note
            pages = @($pageKeys | Where-Object { Test-Page $sha $_ $v.Paths }); taken = (Test-Path "$out\$($v.Key)\home_pc.jpg") }
    }
    ConvertTo-Json @($list) -Depth 4 | Set-Content -Encoding utf8 "$out\versions.json"
    docker run --rm -v "${Root}\e2e:/e2e" -v "${out}:/out" $image python /e2e/showcase_gallery.py
    if ($LASTEXITCODE -ne 0) { throw 'Making the gallery failed.' }
    $result = 0
    Write-Host "Done: open $out\index.html" -ForegroundColor Green
} catch {
    Write-Host $_ -ForegroundColor Red
} finally {
    Write-Host 'Removing the showcase copy...' -ForegroundColor Cyan
    Remove-Copy
    Remove-Item "$work\media", "$work\backups" -Recurse -Force -ErrorAction SilentlyContinue
    git worktree prune
}
exit $result
