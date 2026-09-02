<#
.SYNOPSIS
    Stage a fully self-contained, offline BAIF Bhasha bundle for another Windows machine.

.DESCRIPTION
    Produces ONE folder that the receiving machine can set up with no internet
    access at all -- no pip downloads, no Hugging Face login, no
    scripts\download_models.py run, no npm install, no Node.js.

    Layout produced:

        <OutDir>\
          README-FIRST.txt          human instructions
          setup.ps1                 one command to install on the target
          run.ps1                   one command to start the app
          verify_offline.py         proves the models resolve with no network
          app\                      the project source + pre-downloaded models
          wheelhouse\               every Python dependency as a .whl
          requirements-offline.txt  the exact pinned set to install from wheelhouse
          bin\                      ffmpeg.exe / ffprobe.exe
          installers\               Python 3.12 + VC++ redistributable
          MANIFEST.txt              what went in, and how big

    Run this from the repo root's PowerShell, with backend\.venv already built
    and working -- this script reuses that venv to build the wheelhouse, so the
    wheels match a known-good install.

.PARAMETER OutDir
    Where to stage the bundle. Needs ~15 GB free. Must be outside the repo --
    otherwise the copy step would recurse into its own output.

.PARAMETER SkipDownloads
    Do not fetch ffmpeg / Python / VC++ redist from the internet. Use if you
    have already placed them in bin\ and installers\ yourself.

.PARAMETER SkipWheelhouse
    Reuse an existing <OutDir>\wheelhouse instead of rebuilding it (the slowest
    network step). Only safe if requirements have not changed since.

.PARAMETER PythonVersion
    Which CPython 3.12.x installer to bundle. Must be a 3.12 release: the
    wheelhouse is built for cp312 and will not install on 3.13+.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\offline\build-bundle.ps1 -OutDir D:\baif-offline
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutDir,

    [switch]$SkipDownloads,
    [switch]$SkipWheelhouse,
    [switch]$SkipFrontendBuild,

    [string]$PythonVersion = '3.12.10'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is far faster without it

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Backend  = Join-Path $RepoRoot 'backend'
$Frontend = Join-Path $RepoRoot 'frontend'
$Venv     = Join-Path $Backend '.venv'

# Model caches that exist on the dev machine but that nothing in the app loads.
# Both Whisper pipelines are pinned to "medium" (vendor/video_baif's MODEL_SIZE
# and vendor/audio_ba's ASR_MODEL), so the "small" download is dead weight.
#
# models--google--flan-t5-large looks like the same kind of leftover and is NOT
# excluded, deliberately: vendor/audio_ba/modules/audio/tts.py:60 builds its
# description tokenizer from `self.model.config.text_encoder._name_or_path`,
# which resolves at runtime to "google/flan-t5-large". Nothing greps for that
# string, so the dependency is invisible in the source -- but drop the cache and
# dubbing dies offline trying to fetch a tokenizer it can never reach. It is
# 3.2 MB of tokenizer files (no weights; those live inside parler-tts's own
# safetensors), so keeping it costs nothing.
$UnusedModelCaches = @(
    'models--Systran--faster-whisper-small'
)

function Write-Step { param([string]$Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Note { param([string]$Message) Write-Host "    $Message" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Message) Write-Host "    ! $Message" -ForegroundColor Yellow }

function Invoke-Robocopy {
    <#
        robocopy without /SL follows symbolic links and copies the target's
        CONTENT, which is exactly what is wanted here: the shipped Hugging Face
        cache must not contain reparse points, because those break on
        extraction and on machines without Developer Mode enabled. The
        straggler sweep after the copy re-checks that nothing survived.

        Exit codes 0-7 are success (8+ is a real failure), and robocopy always
        sets a nonzero code, so $LASTEXITCODE has to be normalised or the
        caller's next success check misreads it.
    #>
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExtraArgs = @()
    )

    $rcArgs = @($Source, $Destination, '/E', '/R:2', '/W:2', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/MT:16') + $ExtraArgs
    & robocopy.exe @rcArgs | Out-Null
    $code = $LASTEXITCODE
    $global:LASTEXITCODE = 0
    if ($code -ge 8) { throw "robocopy failed (exit $code): $Source -> $Destination" }
}

function Get-FolderSize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return [int64]0 }
    $m = Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    if ($null -eq $m.Sum) { return [int64]0 }
    return [int64]$m.Sum
}

function Format-GB { param([double]$Bytes) '{0:N2} GB' -f ($Bytes / 1GB) }

# ----------------------------------------------------------------------
# 0. Preflight
# ----------------------------------------------------------------------

Write-Step 'Preflight'

if (-not (Test-Path (Join-Path $Backend 'requirements-cpu.txt'))) {
    throw "Not a BAIF Bhasha checkout: $RepoRoot"
}

$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if ($OutDir.TrimEnd('\').StartsWith($RepoRoot.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw "-OutDir must be outside the repo ($OutDir is inside $RepoRoot); the copy step would recurse into its own output."
}

$VenvPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    throw "backend\.venv not found. Build it first (PACKAGING.md step 2) -- this script reuses it to produce the wheelhouse."
}

$venvVersion = (& $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
if ($venvVersion -ne '3.12') {
    throw "backend\.venv is Python $venvVersion, not 3.12. Its wheelhouse would be tagged cp$($venvVersion -replace '\.','') and would refuse to install on the 3.12 this bundle ships."
}
Write-Note "venv Python $venvVersion -- wheelhouse will be cp312/win_amd64"

if (-not $PythonVersion.StartsWith('3.12.')) {
    throw "-PythonVersion must be a 3.12.x release (got $PythonVersion); the cp312 wheelhouse will not install on anything else."
}

$hfToken = Join-Path $Backend 'data\hf_cache\token'
if (Test-Path $hfToken) {
    Write-Warn 'Hugging Face token found at backend\data\hf_cache\token -- it is NOT copied into the bundle (only hub\ and modules\ are).'
}

$driveFree = (Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($OutDir).TrimEnd('\:'))).Free
Write-Note "Target drive free: $(Format-GB $driveFree)"
if ($driveFree -lt 15GB) {
    Write-Warn 'Less than 15 GB free. The staged bundle is ~12.5 GB, and the wheelhouse build needs temp space on top of that.'
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# ----------------------------------------------------------------------
# 1. Frontend: build with the mock OFF, then prove it
# ----------------------------------------------------------------------

Write-Step 'Building frontend (VITE_USE_MOCK=false)'

if ($SkipFrontendBuild) {
    Write-Note 'Skipped by request -- reusing the existing frontend\dist'
} else {
    Push-Location $Frontend
    try {
        $env:VITE_USE_MOCK = 'false'
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item Env:\VITE_USE_MOCK -ErrorAction SilentlyContinue
        Pop-Location
    }
}

# src/api/index.js does `String(import.meta.env.VITE_USE_MOCK) !== 'false'`.
# Vite inlines the env var, but Rollup cannot constant-fold through String(),
# so mock.js and its sample Devanagari text stay in the bundle either way --
# their presence proves nothing. The inlined literal is what actually decides
# it, so that is what gets asserted here.
$bundleJs = Get-ChildItem (Join-Path $Frontend 'dist\assets\*.js') | Select-Object -First 1
if (-not $bundleJs) { throw 'frontend\dist\assets contains no JS -- the build produced no bundle.' }
$bundleText = Get-Content -LiteralPath $bundleJs.FullName -Raw
if ($bundleText -notmatch '=\s*"false"\s*,\s*\w+\s*=\s*String\(\w+\)\s*!==\s*"false"') {
    throw "Built bundle has no inlined VITE_USE_MOCK=`"false`" literal, so it would ship the in-memory FAKE backend. Inspect $($bundleJs.Name)."
}
Write-Note "$($bundleJs.Name): mock flag verified OFF"

# ----------------------------------------------------------------------
# 2. Project source
# ----------------------------------------------------------------------

Write-Step 'Copying project source'

$AppDir = Join-Path $OutDir 'app'

# Full paths, not bare directory names: a bare `/XD dist` would also drop
# frontend\dist, which is the built UI this bundle specifically needs.
$excludeDirs = @(
    (Join-Path $RepoRoot '.git'),
    (Join-Path $Backend '.venv'),
    (Join-Path $Backend '.venv-gpu'),
    (Join-Path $Backend 'build'),
    (Join-Path $Backend 'dist'),
    (Join-Path $Backend 'data'),
    (Join-Path $Frontend 'node_modules'),
    '__pycache__',
    '.pytest_cache'
)

Invoke-Robocopy -Source $RepoRoot -Destination $AppDir `
    -ExtraArgs (@('/XD') + $excludeDirs + @('/XF', '*.pyc', '*.log', '.env', '.env.local'))

# If someone ran setup.ps1 against a previous staging of this bundle to test it,
# a venv is sitting in the output. robocopy has no /PURGE here, so it survives
# a rebuild -- and a venv is not relocatable (pyvenv.cfg records an absolute
# `home`), so shipping it means handing over 2 GB that cannot work on the other
# machine. setup.ps1 now detects and rebuilds such a venv, but not shipping one
# is better than repairing it there.
$stagedVenv = Join-Path $AppDir 'backend\.venv'
if (Test-Path $stagedVenv) {
    Write-Warn 'Removing a venv left in the staging output by a previous setup.ps1 test run.'
    Remove-Item -LiteralPath $stagedVenv -Recurse -Force
}

Write-Note "source -> app\  ($(Format-GB (Get-FolderSize $AppDir)))"

# ----------------------------------------------------------------------
# 3. Models
# ----------------------------------------------------------------------

Write-Step 'Copying model weights'

$srcData = Join-Path $Backend 'data'
$dstData = Join-Path $AppDir 'backend\data'

# IndicTrans2 is loaded by local path (vendor/docs_baif/config.py ->
# TRANSLATION_MODEL_DIR), and each checkpoint dir carries its own
# configuration_indictrans.py / modeling_indictrans.py, so trust_remote_code
# resolves from disk with no network.
Invoke-Robocopy -Source (Join-Path $srcData 'models') -Destination (Join-Path $dstData 'models')
Write-Note "models\           $(Format-GB (Get-FolderSize (Join-Path $dstData 'models')))"

# Hugging Face hub cache: whisper-medium, nllb-200, parler-tts.
$hubExcludes = @('/XD', (Join-Path $srcData 'hf_cache\hub\.locks'))
foreach ($unused in $UnusedModelCaches) {
    $hubExcludes += (Join-Path $srcData "hf_cache\hub\$unused")
}
Invoke-Robocopy -Source (Join-Path $srcData 'hf_cache\hub') -Destination (Join-Path $dstData 'hf_cache\hub') -ExtraArgs $hubExcludes

# transformers writes IndicTrans2's custom model code out here on first load.
# Tiny, but ship it: with HF_HUB_OFFLINE=1 there is no way to refetch it.
Invoke-Robocopy -Source (Join-Path $srcData 'hf_cache\modules') -Destination (Join-Path $dstData 'hf_cache\modules') -ExtraArgs @('/XD', '__pycache__')

Write-Note "hf_cache\         $(Format-GB (Get-FolderSize (Join-Path $dstData 'hf_cache')))"

# --- no reparse points may survive into the bundle ---------------------
$stragglers = Get-ChildItem -LiteralPath (Join-Path $dstData 'hf_cache') -Recurse -Force -ErrorAction SilentlyContinue |
              Where-Object { $_.LinkType }
if ($stragglers) {
    Write-Warn "$($stragglers.Count) symlink(s) survived the copy; realising them by hand."
    foreach ($link in $stragglers) {
        $target = (Get-Item -LiteralPath $link.FullName -Force).Target
        if ($target -is [array]) { $target = $target[0] }
        if (-not $target) { throw "Cannot resolve the symlink target for $($link.FullName)" }
        if (-not [System.IO.Path]::IsPathRooted($target)) {
            $target = Join-Path (Split-Path -Parent $link.FullName) $target
        }
        Remove-Item -LiteralPath $link.FullName -Force
        Copy-Item -LiteralPath $target -Destination $link.FullName -Force
    }
}

# --- drop blobs\ once snapshots\ holds the real bytes ------------------
# huggingface_hub normally puts real files in blobs\ and symlinks them into
# snapshots\. Once the copy above has turned those links into real files,
# blobs\ is a byte-for-byte duplicate -- 2.3 GB of it for NLLB alone.
# Dropping it is not a guess: whisper-medium and parler-tts in this very cache
# already have an empty blobs\ alongside real snapshot files, and both load
# fine offline today. The empty blobs\ directory is kept, matching that shape.
Write-Step 'De-duplicating the Hugging Face cache'
foreach ($modelDir in Get-ChildItem -LiteralPath (Join-Path $dstData 'hf_cache\hub') -Directory) {
    $blobs = Join-Path $modelDir.FullName 'blobs'
    $snaps = Join-Path $modelDir.FullName 'snapshots'
    if (-not (Test-Path $blobs)) { continue }

    $blobBytes = Get-FolderSize $blobs
    if ($blobBytes -eq 0) { continue }

    $snapBytes = Get-FolderSize $snaps
    if ($snapBytes -ge $blobBytes) {
        Get-ChildItem -LiteralPath $blobs -File -Force | Remove-Item -Force
        Write-Note "$($modelDir.Name): freed $(Format-GB $blobBytes) (snapshots hold $(Format-GB $snapBytes))"
    } else {
        Write-Warn "$($modelDir.Name): snapshots ($(Format-GB $snapBytes)) are smaller than blobs ($(Format-GB $blobBytes)); keeping blobs."
    }
}

# Job uploads/outputs from local testing are not part of a clean handoff, and
# may contain files you did not mean to send.
Write-Note 'backend\data\jobs is deliberately NOT copied (local test data).'

# ----------------------------------------------------------------------
# 4. Wheelhouse
# ----------------------------------------------------------------------

$WheelDir = Join-Path $OutDir 'wheelhouse'
$ReqOffline = Join-Path $OutDir 'requirements-offline.txt'

Write-Step 'Building the pip wheelhouse'

if ($SkipWheelhouse -and (Test-Path $WheelDir)) {
    Write-Note 'Skipped by request -- reusing the existing wheelhouse'
} else {
    Remove-Item -LiteralPath $WheelDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

    # `pip wheel`, not `pip download`, because parler_tts and its own git
    # dependency descript-audiotools are direct git URLs: this builds them into
    # ordinary wheels, so the target machine needs neither git nor network.
    & $VenvPython -m pip wheel `
        -r (Join-Path $Backend 'requirements-cpu.txt') `
        -w $WheelDir `
        --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) {
        throw "pip wheel failed (exit $LASTEXITCODE). Every dependency has to build to a wheel here, on the machine WITH network, or the target install cannot be offline."
    }
}

$wheels = Get-ChildItem (Join-Path $WheelDir '*.whl')
if ($wheels.Count -eq 0) { throw "wheelhouse is empty: $WheelDir" }

# Install by pinned name==version rather than by passing every .whl path:
# ~200 absolute paths on one command line runs at the Windows 32767-char limit.
$pins = foreach ($w in $wheels) {
    $parts = $w.BaseName -split '-'
    '{0}=={1}' -f $parts[0], $parts[1]
}
$header = @(
    '# Generated by packaging/offline/build-bundle.ps1 -- do not edit.',
    '# Install with:',
    '#   pip install --no-index --find-links wheelhouse -r requirements-offline.txt',
    "# Built from backend/requirements-cpu.txt against CPython $venvVersion / win_amd64."
)
# WriteAllLines with an explicit no-BOM encoding, not Set-Content -Encoding utf8:
# Windows PowerShell 5.1's utf8 always emits a BOM, which lands in front of the
# first comment. pip happens to strip it, but a requirements file has no reason
# to carry one.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($ReqOffline, ($header + ($pins | Sort-Object -Unique)), $utf8NoBom)

$nonWin = $wheels | Where-Object { $_.Name -notmatch 'win_amd64|none-any' }
if ($nonWin) {
    Write-Warn "$($nonWin.Count) wheel(s) are neither win_amd64 nor pure-Python -- check them: $($nonWin.Name -join ', ')"
}
Write-Note "$($wheels.Count) wheels, $(Format-GB (Get-FolderSize $WheelDir))"

# ----------------------------------------------------------------------
# 5. ffmpeg, Python, VC++ redistributable
# ----------------------------------------------------------------------

$BinDir = Join-Path $OutDir 'bin'
$InstallerDir = Join-Path $OutDir 'installers'
New-Item -ItemType Directory -Force -Path $BinDir, $InstallerDir | Out-Null

Write-Step 'Fetching bundled binaries and installers'

if ($SkipDownloads) {
    Write-Note 'Skipped by request -- bin\ and installers\ left as they are'
} else {
    # ffmpeg: vendor/video_baif shells out to a bare "ffmpeg" for audio
    # extraction and subtitle burn-in. Only the video pipeline needs it.
    if (Test-Path (Join-Path $BinDir 'ffmpeg.exe')) {
        Write-Note 'ffmpeg.exe already present, skipping'
    } else {
        $zip = Join-Path $env:TEMP 'ffmpeg-release-essentials.zip'
        $extract = Join-Path $env:TEMP 'ffmpeg-extract'
        Write-Note 'Downloading ffmpeg (gyan.dev essentials build) ...'
        Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
        Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force
        Get-ChildItem -LiteralPath $extract -Recurse -Filter 'ff*.exe' |
            Where-Object { $_.Name -eq 'ffmpeg.exe' -or $_.Name -eq 'ffprobe.exe' } |
            ForEach-Object { Copy-Item $_.FullName -Destination $BinDir -Force }
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue
    }

    $pyExe = Join-Path $InstallerDir "python-$PythonVersion-amd64.exe"
    if (Test-Path $pyExe) {
        Write-Note "python-$PythonVersion-amd64.exe already present, skipping"
    } else {
        $pyUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
        Write-Note "Downloading CPython $PythonVersion ..."
        try {
            Invoke-WebRequest -Uri $pyUrl -OutFile $pyExe
        } catch {
            Remove-Item -LiteralPath $pyExe -Force -ErrorAction SilentlyContinue
            throw "Could not download $pyUrl -- pick a real 3.12.x from https://www.python.org/downloads/ and pass it as -PythonVersion. It MUST be 3.12: the wheelhouse is cp312-only."
        }
    }

    # torch, ctranslate2 and onnxruntime all link the MSVC runtime. Present on
    # most Win11 boxes, but a freshly imaged machine may not have it.
    $vcExe = Join-Path $InstallerDir 'vc_redist.x64.exe'
    if (Test-Path $vcExe) {
        Write-Note 'vc_redist.x64.exe already present, skipping'
    } else {
        Write-Note 'Downloading the VC++ 2015-2022 redistributable ...'
        Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $vcExe
    }
}

if (-not (Test-Path (Join-Path $BinDir 'ffmpeg.exe'))) {
    Write-Warn 'No ffmpeg.exe in bin\ -- VIDEO jobs will fail on the target machine.'
}

# ----------------------------------------------------------------------
# 6. Target-side scripts and docs
# ----------------------------------------------------------------------

Write-Step 'Adding setup/run scripts'

Copy-Item (Join-Path $PSScriptRoot 'bundle\*') -Destination $OutDir -Recurse -Force -Exclude '__pycache__'
Remove-Item -LiteralPath (Join-Path $OutDir '__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
Write-Note 'setup.ps1, run.ps1, verify_offline.py, README-FIRST.txt'

# ----------------------------------------------------------------------
# 6b. Verify the staged bundle before anyone moves 12 GB across a room
# ----------------------------------------------------------------------

Write-Step 'Verifying the staged bundle'

# --bundle is strict about symlinks: one that still resolves here, on the
# machine that has the blobs, would arrive on the target as a dangling link.
# Run it with the build venv, since the bundle's own venv does not exist yet.
& $VenvPython (Join-Path $OutDir 'verify_offline.py') --bundle
if ($LASTEXITCODE -ne 0) {
    throw 'Bundle verification FAILED (see above). Do not ship this folder -- fix the problem and re-run.'
}
Write-Note 'Add --full to load every model with the network blocked (slow, but the real proof).'

# ----------------------------------------------------------------------
# 7. Manifest
# ----------------------------------------------------------------------

Write-Step 'Writing MANIFEST.txt'

$sections = [ordered]@{
    'app (source + models)' = $AppDir
    '  models\translation'  = (Join-Path $AppDir 'backend\data\models')
    '  hf_cache'            = (Join-Path $AppDir 'backend\data\hf_cache')
    '  frontend\dist'       = (Join-Path $AppDir 'frontend\dist')
    'wheelhouse'            = $WheelDir
    'bin'                   = $BinDir
    'installers'            = $InstallerDir
}

$lines = @(
    'BAIF Bhasha -- offline bundle',
    "Built:            $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Built on:         $env:COMPUTERNAME",
    "Source:           $RepoRoot",
    "Python target:    CPython $PythonVersion (cp312 / win_amd64) -- REQUIRED, not optional",
    "Wheels:           $($wheels.Count)",
    "Frontend:         $($bundleJs.Name), VITE_USE_MOCK=false verified",
    'Whisper:          medium (shared by the audio and video pipelines)',
    "Excluded:         backend\data\jobs, hf_cache\token, $($UnusedModelCaches -join ', ')",
    ''
)
foreach ($key in $sections.Keys) {
    $lines += '{0,-24} {1,12}' -f $key, (Format-GB (Get-FolderSize $sections[$key]))
}
$total = Get-FolderSize $OutDir
$lines += ''
$lines += '{0,-24} {1,12}' -f 'TOTAL', (Format-GB $total)

[System.IO.File]::WriteAllLines((Join-Path $OutDir 'MANIFEST.txt'), $lines, $utf8NoBom)
$lines | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

Write-Host "`nBundle staged at $OutDir ($(Format-GB $total))" -ForegroundColor Green
Write-Host 'Next: verify it, then transfer the whole folder. See packaging\offline\README.md.' -ForegroundColor Green
