# Packaging BAIF Bhasha into a distributable app

The shipped artifact is a PyInstaller `--onedir` bundle: a folder with a
`baif-bhasha` launcher, all Python dependencies, **and** the ML model weights
baked in. The model download is the slow, network-dependent, occasionally
gated-access step — do it once, first, on whatever machine has good internet
and time to spare, then everything downstream (building, copying to the demo
machine, running) is fast and fully offline.

**Fastest path for a live demo**: if you're short on time, you don't need a
built executable at all — steps 1, 2, and 4 below get you a working app via
`python run.py` (step 5). Treat step 3 (the actual PyInstaller build) as
optional polish once the app itself is working.

**Handing the project to another machine instead of a binary**: see
`packaging/offline/README.md`. One `build-bundle.ps1` run stages a ~11 GB
folder — source, models, a pip wheelhouse, a prebuilt UI, ffmpeg and a Python
installer — that sets up on a second Windows box with two commands and no
internet: no PyPI, no Hugging Face login, no `download_models.py`, no Node.js,
no `git`. Use that when the recipient should have the actual project rather
than a frozen `.exe`.

## 1. Build the frontend

```bash
cd frontend
npm install
VITE_USE_MOCK=false npm run build
```

This produces `frontend/dist/`, which the backend serves directly — no
Node.js is needed after this step.

## 2. Create the backend environment

Use Python 3.12 (torch/transformers wheels for this stack are not yet
reliable on 3.13+).

CPU and GPU builds need different torch wheels, so they live in separate
requirements files — `requirements-cpu.txt` and `requirements-gpu.txt` —
which both pull the rest of the dependency set in from the shared
`requirements.txt` (that file alone has no torch build in it and is not
meant to be installed directly). Use the CPU one unless you're doing the
GPU build in step 6b:

**macOS / Linux:**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-cpu.txt
```

**Windows (PowerShell)** — the primary target for this app's packaged build:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-cpu.txt
```

If activation is blocked by the execution policy, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal
first.

`parler_tts` installs from GitHub (its own setup.py pulls in
`descript-audiotools` from git too) — this step needs `git` and network
access once. Don't also add `descript-audiotools` as its own line in
`requirements.txt`: pip treats a separately-pinned direct-URL requirement for
the same package as a conflicting specifier even when it would resolve to
the same commit, and the install fails.

If you don't need the audio-dubbing bonus feature and want a smaller/faster
install, drop the `parler_tts` and `descript-audio-codec` lines from
`requirements.txt` — the rest of the app (documents, video subtitles, audio
transcript+translation) works fine without them; only
`POST /api/jobs/{id}/dubbed-audio` becomes unreachable.

## 3. Download the models (do this once, early)

```bash
python scripts/download_models.py
```

This fetches, into `backend/data/`:
1. Three IndicTrans2 checkpoints (~3.1 GB combined) — used by the document
   and audio pipelines.
2. **NLLB-200 distilled 600M** (~2.4 GB) — used by the *video* pipeline,
   which translates with NLLB rather than IndicTrans2. Not gated, so no
   Hugging Face login needed for this one. `--skip-video-translation`
   leaves it out (video jobs then fail at the translation step).
3. faster-whisper `medium` (~1.5 GB) — shared by the audio and video
   pipelines. Video was raised from `small` to `medium` for better Indic
   accuracy, which conveniently means only one Whisper model ships.
4. Indic Parler-TTS (~3.6 GB) — only needed for the audio-dubbing bonus;
   pass `--skip-tts` to leave it out and save real time/bandwidth.

The two large single-file downloads (NLLB and Parler-TTS) are the ones
that tend to time out on a slow link; the script retries and
huggingface_hub resumes from the partial file rather than restarting.

**Four of these repos are gated on Hugging Face** (everything except
faster-whisper and NLLB-200) and this is the one step that needs a human,
not just a script:
1. Log into a Hugging Face account and request/accept access on each page:
   - https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
   - https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
   - https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M
   - https://huggingface.co/ai4bharat/indic-parler-tts (skip if using `--skip-tts`)

   The three IndicTrans2 ones are usually instant. `indic-parler-tts` says
   "authorized list" rather than a plain agree-and-go gate, so it may take
   longer or need manual review — if you're short on time, use `--skip-tts`
   and come back to it later; nothing else depends on it.
2. Authenticate this shell: `huggingface-cli login` (paste a token from
   https://huggingface.co/settings/tokens), or `export HF_TOKEN=hf_...`.
3. Re-run `python scripts/download_models.py` (already-downloaded models are
   skipped automatically, so it's safe to re-run after getting access to
   just one more repo).

Without access, the script fails with `GatedRepoError` and prints these same
steps for whichever repo it hit.

`GET /api/status` reports each model's `loaded` state once the app is
running, so the frontend can show setup progress instead of a silent hang.

## 4. Run it directly (good enough for a demo)

```bash
python run.py
```

Starts the server on `http://127.0.0.1:8000` and opens it in the default
browser. This is everything needed to demo the app on the current machine —
no PyInstaller build required. Change host/port with `BAIF_HOST` /
`BAIF_PORT`.

## 5. (Optional) Build a standalone executable

```bash
pyinstaller pyinstaller.spec
```

Output lands in `backend/dist/baif-bhasha/` (this works the same on Windows
as on macOS/Linux — just run it from the PowerShell venv above; the launcher
is named `baif-bhasha.exe` there). This bundles whatever's already in
`backend/data/models` and `backend/data/hf_cache` at build time (see step 3)
directly into the app, so the built folder runs fully offline on another
machine with no download or Hugging Face login needed there. Copy the whole
`backend/dist/baif-bhasha/` folder to the target machine and run the
`baif-bhasha` (or `baif-bhasha.exe`) launcher inside it.

`ffmpeg` is not bundled by the spec file — copy an `ffmpeg` binary for the
target OS into the built folder (or ensure it's already on `PATH` there); the
video pipeline shells out to it for audio extraction. **On Windows**:
download a static build (e.g. the "essentials" build from
https://www.gyan.dev/ffmpeg/builds/ or from
https://github.com/BtbN/FFmpeg-Builds/releases), and copy just `ffmpeg.exe`
directly into `backend\dist\baif-bhasha\` next to `baif-bhasha.exe` — no
system PATH changes needed, since Windows always checks the launcher's own
folder first.

## 6. (Optional) Build a Windows installer

Wraps the `backend\dist\baif-bhasha\` folder from step 5 (with `ffmpeg.exe`
already copied in, per the note above) into a proper installer — Start Menu
shortcut, uninstaller entry in "Add or remove programs" — instead of asking
someone to copy a raw folder around.

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) installed on the
build machine (a new external tool, not otherwise part of this repo).

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
```

Run from the repo root, after step 5 has produced
`backend\dist\baif-bhasha\`. Output is
`packaging\windows\output\BAIF-Bhasha-Setup.exe` — a single installer that
copies everything into `Program Files`, adds a Start Menu shortcut, and
registers an uninstaller. See the comment header in
`packaging/windows/installer.iss` for what it bundles.

## 6b. GPU build variant (optional)

The default install (step 2, `requirements-cpu.txt`) pulls a **CPU-only**
torch build — it has no NVIDIA driver dependency at all, so it's guaranteed
to run on any Windows machine, GPU or not. That also means the "Process on
GPU" toggle in the UI will always show as unavailable in a normally-built
app, even on a machine with a good GPU: a CPU-only torch build has no CUDA
support compiled in to turn on, regardless of the hardware.

If you specifically know the target/demo machine has an NVIDIA GPU and a
recent driver (check with `nvidia-smi`), build a **separate GPU-enabled
installer** instead of changing the default one. Use a fresh venv (or
`pip uninstall torch torchaudio -y` in the existing one first) and install
`requirements-gpu.txt` instead of `requirements-cpu.txt`:

```powershell
cd backend
py -3.12 -m venv .venv-gpu
.venv-gpu\Scripts\Activate.ps1
pip install -r requirements-gpu.txt
```

`requirements-gpu.txt` pins the `cu121` CUDA wheel tag as an example — check
https://pytorch.org/get-started/locally/ and, if a different tag is needed
(pick Windows / Pip / Python / whatever CUDA version is closest to, but not
newer than, what `nvidia-smi` reports as supported), update the
`--extra-index-url` line and the `+cuXXX` version suffixes in that file to
match before installing. Verify before continuing:

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Then build and package exactly as steps 4–6 (from this GPU venv), but set
`BAIF_BUILD_VARIANT=gpu` before compiling the installer so the output is
clearly labelled and never mistaken for the CPU one:

```powershell
pyinstaller pyinstaller.spec
# copy ffmpeg.exe in, same as step 5
$env:BAIF_BUILD_VARIANT = "gpu"
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
```

Output is `packaging\windows\output\BAIF-Bhasha-Setup-GPU.exe`. Both
variants share one app identity in Windows (same `AppId` in
`installer.iss`), so installing one over the other upgrades in place rather
than leaving two copies — don't install both side by side on the same
machine.

**Only build this variant on hardware you've confirmed has a working NVIDIA
driver.** A GPU-enabled torch build's DLLs depend on the driver being
present to load correctly; the backend guards every CUDA check with a
`try/except` that falls back to reporting "no GPU" rather than crashing (see
`app/core/device.py`'s `gpu_available()`), but that safety net is about
avoiding a *crash* on a driver-less machine, not about making CUDA actually
usable there — for that, the machine still needs a real GPU and driver.

## 6c. Building on a roomier drive

The `--onedir` build with models baked in is easily 5-15+ GB, and Inno
Setup's own single-file `Setup.exe` output is capped at ~4.2 GB (it errors
with "Disk spanning must be enabled..." past that, unless you actually want
a multi-file spanned installer). If the system drive doesn't have room for
the build, models, and installer output all at once, point the heavy steps
at another drive instead of moving the whole repo:

```powershell
# Step 4 -- send the PyInstaller output to another drive:
pyinstaller pyinstaller.spec --distpath D:\baif-build\dist --workpath D:\baif-build\build

# Step 6 -- tell installer.iss where that output landed, and send the
# compiled installer there too instead of packaging\windows\output:
$env:BAIF_BUILD_DIR = "D:\baif-build\dist\baif-bhasha"
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /O"D:\baif-build\output" packaging\windows\installer.iss
```

To shrink the build itself rather than relocate it, set
`BAIF_PACKAGE_SKIP_TTS=1` before step 4 to leave the Parler-TTS weights (by
far the largest single model, several GB) out of what gets bundled — same
idea as `download_models.py --skip-tts`, but applied at packaging time so
you can keep the weights cached locally for dev use while still shipping a
smaller installer. A build made this way will fail a job that has "Include
dubbing" checked (no cached weights, no internet on the target machine)
instead of producing a dubbed track.

## Notes

- Model weights and job data live under `backend/data/` (`BAIF_DATA_DIR` to
  override the whole thing; `HF_HOME` is redirected to `data/hf_cache`
  specifically so faster-whisper/Parler-TTS downloads land somewhere
  predictable and bundleable instead of the default `~/.cache/huggingface`).
- The `--onedir` build (not `--onefile`) is deliberate: PyInstaller's
  `--onefile` mode unpacks itself to a temp directory on every launch, which
  is slow and wasteful for an app this size (torch, transformers, PyMuPDF,
  model weights, etc.). `--onedir` starts instantly after the first launch.
- A built `backend/dist/baif-bhasha/` folder with all models included will be
  several GB — expected, given three translation checkpoints plus
  faster-whisper plus (optionally) Parler-TTS. Skip `--skip-tts` in step 3 if
  that's too large to move around during the event.
