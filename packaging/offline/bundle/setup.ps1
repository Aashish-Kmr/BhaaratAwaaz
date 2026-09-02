<#
.SYNOPSIS
    One-command, fully offline setup for BAIF Bhasha on a fresh Windows machine.

.DESCRIPTION
    Run this once, from the folder it sits in. It does not touch the internet.

      1. Installs CPython 3.12 from installers\ if it is not already here
      2. Installs the VC++ runtime that torch / ctranslate2 / onnxruntime need
      3. Creates app\backend\.venv
      4. Installs every dependency from wheelhouse\ -- no PyPI, no git
      5. Puts ffmpeg.exe where an activated venv will find it
      6. Verifies that every model resolves with the network blocked

    The models are already in app\backend\data. Do NOT run
    scripts\download_models.py -- there is nothing left for it to fetch, and it
    turns HF_HUB_OFFLINE back off.

.PARAMETER SkipVerify
    Skip step 6's slow --full model load. The fast file checks still run.

.PARAMETER Force
    Delete and rebuild app\backend\.venv if it already exists.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipVerify,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Root         = $PSScriptRoot
$AppDir       = Join-Path $Root 'app'
$BackendDir   = Join-Path $AppDir 'backend'
$VenvDir      = Join-Path $BackendDir '.venv'
$VenvPython   = Join-Path $VenvDir 'Scripts\python.exe'
$VenvScripts  = Join-Path $VenvDir 'Scripts'
$WheelDir     = Join-Path $Root 'wheelhouse'
$BinDir       = Join-Path $Root 'bin'
$InstallerDir = Join-Path $Root 'installers'
$ReqOffline   = Join-Path $Root 'requirements-offline.txt'

function Write-Step { param([string]$m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Warn { param([string]$m) Write-Host "    ! $m" -ForegroundColor Yellow }

function Update-PathFromRegistry {
    # A just-run installer writes PATH to the registry, but this already-open
    # session keeps its stale copy until it is re-read by hand.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @($machine, $user) | Where-Object { $_ }
    $env:Path = $parts -join ';'
}

function Find-Python312 {
    <#
        Returns the path to a CPython 3.12 interpreter, or $null.
        3.12 specifically: the wheelhouse is tagged cp312 and pip will refuse
        every wheel in it on 3.11 or 3.13+.
    #>
    $candidates = @()

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $resolved = & $pyLauncher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates += $resolved.Trim() }
    }

    $candidates += @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        'C:\Python312\python.exe',
        (Join-Path $env:ProgramFiles 'Python312\python.exe')
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            $version = (& $candidate -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null)
            if ($version -and $version.Trim() -eq '3.12') { return $candidate }
        }
    }
    return $null
}

# ----------------------------------------------------------------------

Write-Host 'BAIF Bhasha -- offline setup' -ForegroundColor Green
Write-Host "Bundle: $Root" -ForegroundColor DarkGray

foreach ($required in @($AppDir, $WheelDir, $ReqOffline)) {
    if (-not (Test-Path $required)) {
        throw "Incomplete bundle: $required is missing. Re-copy the whole folder -- a partial transfer cannot be fixed here."
    }
}

# ----------------------------------------------------------------------
# 1. Python 3.12
# ----------------------------------------------------------------------

Write-Step 'Locating CPython 3.12'

$python = Find-Python312
if ($python) {
    Write-Note "Found $python"
} else {
    $installer = Get-ChildItem (Join-Path $InstallerDir 'python-3.12.*-amd64.exe') -ErrorAction SilentlyContinue |
                 Select-Object -First 1
    if (-not $installer) {
        throw 'No Python 3.12 on this machine and no installer in installers\. Install CPython 3.12 (not 3.13+) and re-run.'
    }

    Write-Note "Installing $($installer.Name) (per-user, no admin needed) ..."
    # Per-user install avoids the UAC prompt; PrependPath + the py launcher are
    # what make `py -3.12` work in a fresh shell afterwards.
    $proc = Start-Process -FilePath $installer.FullName -Wait -PassThru -ArgumentList @(
        '/passive', 'InstallAllUsers=0', 'PrependPath=1',
        'Include_launcher=1', 'Include_pip=1', 'Include_test=0'
    )
    if ($proc.ExitCode -ne 0) {
        throw "The Python installer exited with $($proc.ExitCode). Run installers\$($installer.Name) by hand, then re-run this script."
    }

    Update-PathFromRegistry
    $python = Find-Python312
    if (-not $python) {
        throw "Python 3.12 installed but could not be found afterwards. Close this window, open a new PowerShell, and re-run setup.ps1."
    }
    Write-Note "Installed at $python"
}

# ----------------------------------------------------------------------
# 2. VC++ runtime
# ----------------------------------------------------------------------

Write-Step 'Checking the Visual C++ runtime'

# torch, ctranslate2 and onnxruntime all link msvcp140.dll. When it is absent
# the failure is an opaque "DLL load failed while importing" at first import,
# so it is worth getting out of the way up front.
$hasRuntime = Test-Path (Join-Path $env:SystemRoot 'System32\msvcp140.dll')
if ($hasRuntime) {
    Write-Note 'msvcp140.dll present'
} else {
    $vc = Join-Path $InstallerDir 'vc_redist.x64.exe'
    if (Test-Path $vc) {
        Write-Note 'Installing the VC++ 2015-2022 redistributable (may prompt for admin) ...'
        $proc = Start-Process -FilePath $vc -Wait -PassThru -ArgumentList @('/install', '/passive', '/norestart')
        # 3010 == success, reboot required.
        if ($proc.ExitCode -notin @(0, 1638, 3010)) {
            Write-Warn ("vc_redist exited with {0}. If importing torch fails later, install it by hand." -f $proc.ExitCode)
        }
    } else {
        Write-Warn 'msvcp140.dll is missing and installers\vc_redist.x64.exe is not in the bundle. torch may fail to import.'
    }
}

# ----------------------------------------------------------------------
# 3. Virtual environment
# ----------------------------------------------------------------------

Write-Step 'Creating the virtual environment'

if ((Test-Path $VenvPython) -and -not $Force) {
    # A venv is not relocatable: pyvenv.cfg records an absolute `home` pointing
    # at the base interpreter, and the Scripts\ stubs bake in absolute paths. If
    # whoever built this bundle ran setup.ps1 before copying it, the .venv in
    # here points at a user profile that does not exist on this machine.
    # Reusing it would fail in confusing ways much later, so ask the
    # interpreter where it thinks it lives and rebuild if it cannot answer.
    $prefix = (& $VenvPython -c "import sys; print(sys.prefix)" 2>$null)
    $sameLocation = $false
    if ($LASTEXITCODE -eq 0 -and $prefix) {
        $sameLocation = [System.IO.Path]::GetFullPath($prefix.Trim()).TrimEnd('\') -ieq
                        [System.IO.Path]::GetFullPath($VenvDir).TrimEnd('\')
    }

    if ($sameLocation) {
        Write-Note '.venv already exists and runs from here -- reusing it. Pass -Force to rebuild.'
    } else {
        Write-Warn '.venv does not run from this location (built on another machine, or moved). Rebuilding it.'
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
} elseif ((Test-Path $VenvDir) -and $Force) {
    Write-Note 'Removing the existing .venv (-Force)'
    Remove-Item -LiteralPath $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed (exit $LASTEXITCODE)" }
}
Write-Note $VenvPython

# ----------------------------------------------------------------------
# 4. Dependencies, entirely from wheelhouse\
# ----------------------------------------------------------------------

Write-Step 'Installing dependencies (offline)'

$wheelCount = (Get-ChildItem (Join-Path $WheelDir '*.whl')).Count
Write-Note "$wheelCount wheels in wheelhouse\"

# --no-index is the whole point: it makes a network attempt impossible rather
# than merely unnecessary, so a gap in the wheelhouse fails here and now
# instead of silently reaching for PyPI on a machine that has no route to it.
& $VenvPython -m pip install `
    --no-index `
    --find-links $WheelDir `
    -r $ReqOffline `
    --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    throw "Offline pip install failed (exit $LASTEXITCODE). If it names a missing distribution, the wheelhouse was built for a different Python -- it must be CPython 3.12 / win_amd64."
}

# ----------------------------------------------------------------------
# 5. ffmpeg
# ----------------------------------------------------------------------

Write-Step 'Installing ffmpeg'

# vendor/video_baif shells out to a bare "ffmpeg", so it has to be resolvable
# on PATH. Dropping it into the venv's Scripts\ means every activated shell
# picks it up with no system PATH change and no admin rights. run.ps1 also
# prepends bin\ for the non-activated case.
$ffmpegBinaries = Get-ChildItem (Join-Path $BinDir '*.exe') -ErrorAction SilentlyContinue
if ($ffmpegBinaries) {
    $ffmpegBinaries | ForEach-Object { Copy-Item $_.FullName -Destination $VenvScripts -Force }
    Write-Note "$($ffmpegBinaries.Name -join ', ') -> .venv\Scripts\"
} else {
    Write-Warn 'No binaries in bin\ -- VIDEO jobs will fail at audio extraction. Documents and audio are unaffected.'
}

# ----------------------------------------------------------------------
# 6. Verify
# ----------------------------------------------------------------------

Write-Step 'Verifying the offline install'

$env:Path = "$VenvScripts;$BinDir;$env:Path"
$verifyArgs = @((Join-Path $Root 'verify_offline.py'))
if (-not $SkipVerify) { $verifyArgs += '--full' } else { Write-Note 'Skipping the --full model load (-SkipVerify)' }

& $VenvPython @verifyArgs
$verifyCode = $LASTEXITCODE

Write-Host ''
if ($verifyCode -eq 0) {
    Write-Host 'Setup complete.' -ForegroundColor Green
    Write-Host ''
    Write-Host '  Start the app:   powershell -ExecutionPolicy Bypass -File run.ps1' -ForegroundColor Green
    Write-Host '  Then open:       http://127.0.0.1:8000' -ForegroundColor Green
} else {
    Write-Host 'Setup finished, but verification FAILED -- see the list above.' -ForegroundColor Red
    Write-Host 'The app may still start; the failing pipeline will not work.' -ForegroundColor Red
    exit 1
}
