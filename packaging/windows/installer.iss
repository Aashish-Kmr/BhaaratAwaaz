; BAIF Bhasha - Windows installer
;
; Wraps the PyInstaller --onedir build (backend\dist\baif-bhasha\) into a
; proper Windows installer: Start Menu shortcut, optional desktop icon, and
; an uninstaller registered in "Add or remove programs".
;
; Build order (see ../../PACKAGING.md for the full walkthrough):
;   1. cd frontend; npm install; $env:VITE_USE_MOCK="false"; npm run build
;   2. cd backend; py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1;
;      pip install -r requirements-cpu.txt   (CPU build; see the GPU note
;      below for the GPU variant -- requirements-cpu.txt and
;      requirements-gpu.txt are separate files precisely because the two
;      builds need different torch wheels; never install both into the
;      same venv)
;   3. python scripts\download_models.py
;   4. pyinstaller pyinstaller.spec        (produces backend\dist\baif-bhasha\)
;   5. Copy ffmpeg.exe into backend\dist\baif-bhasha\ (see PACKAGING.md)
;   6. Compile this script from the repo root with Inno Setup:
;        ISCC.exe packaging\windows\installer.iss
;
; Requires Inno Setup (https://jrsoftware.org/isinfo.php) on the build
; machine -- it is not otherwise a dependency of this repo.
;
; GPU variant: if step 2 instead used a fresh venv with
; `pip install -r requirements-gpu.txt` (see PACKAGING.md "6b. GPU build
; variant"), set BAIF_BUILD_VARIANT=gpu before step 6 so the output is
; clearly labelled and never mistaken for the plain CPU installer:
;     $env:BAIF_BUILD_VARIANT = "gpu"
;     ISCC.exe packaging\windows\installer.iss
;
; Low on space on the system drive? Step 4's --distpath and step 6's
; BAIF_BUILD_DIR (see below) can both point at another drive -- see
; PACKAGING.md's "Building on a roomier drive" note.

#define MyAppName "BAIF Bhasha"
#define MyAppVersion "1.0.0"
#define MyAppExeName "baif-bhasha.exe"

; The PyInstaller onedir output with the ML models baked in easily runs to
; several/many GB (see PACKAGING.md), which can be more than a build
; machine's system drive has free. Set BAIF_BUILD_DIR to point this at a
; `pyinstaller ... --distpath <BAIF_BUILD_DIR>` output on a roomier drive
; instead of the default backend\dist\baif-bhasha next to the repo:
;     $env:BAIF_BUILD_DIR = "D:\baif-build\dist\baif-bhasha"
; Leaving it unset keeps the default in-repo path.
#define MyBuildDirEnv GetEnv("BAIF_BUILD_DIR")
#if MyBuildDirEnv == ""
  #define MyBuildDir "..\..\backend\dist\baif-bhasha"
#else
  #define MyBuildDir MyBuildDirEnv
#endif

; Set BAIF_BUILD_VARIANT=gpu before compiling (ISCC.exe reads it via
; GetEnv) to produce a distinctly-named installer for a build whose venv
; had the CUDA-enabled torch wheel installed -- see PACKAGING.md step 6b.
; Leaving it unset (the default) produces the ordinary CPU-only installer;
; both variants share one AppId so installing one over the other upgrades
; in place rather than creating a duplicate entry.
#define Variant GetEnv("BAIF_BUILD_VARIANT")
#if Variant == "gpu"
  #define VariantSuffix " (GPU)"
  #define OutputSuffix "-GPU"
#else
  #define VariantSuffix ""
  #define OutputSuffix ""
#endif

[Setup]
AppId={{B4A1F0000-BAAF-4B4A-9BAA-BAAFBHASHA001}
AppName={#MyAppName}{#VariantSuffix}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=BAIF-Bhasha-Setup{#OutputSuffix}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; ML model weights make the bundle several GB -- disk space check matters.
DiskSpanning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Recursively bundles the entire PyInstaller onedir output -- launcher,
; Python runtime, all dependencies, and (if present) the baked-in model
; weights and ffmpeg.exe copied in per PACKAGING.md step 5.
Source: "{#MyBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
