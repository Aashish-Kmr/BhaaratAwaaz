================================================================
 BAIF Bhasha -- offline bundle
================================================================

Everything is already in this folder. No internet is needed at any
point: no pip downloads, no Hugging Face account or login, no model
downloads, no Node.js, no git.


 WHAT TO DO
----------------------------------------------------------------

1. Copy this whole folder to a local drive.

   Do not run it from a USB stick or a network share -- the app reads
   several GB of model weights, and that is where the time goes.

2. Open PowerShell in this folder and run:

       powershell -ExecutionPolicy Bypass -File setup.ps1

   Takes 10-25 minutes, mostly the final model-loading check.

3. Start it:

       powershell -ExecutionPolicy Bypass -File run.ps1

   A browser opens at http://127.0.0.1:8000.

That is the whole procedure.


 IF YOU HAVE SEEN THE PROJECT README
----------------------------------------------------------------

Its "Run in development" section does not apply here. Skip these,
they are already done or would actively break things:

  pip install -r requirements-cpu.txt
        Replaced by an offline install from wheelhouse\. Running the
        original needs PyPI and a git clone of parler_tts.

  python scripts\download_models.py
        DO NOT RUN. All 8 models are already in
        app\backend\data. This script also turns HF_HUB_OFFLINE
        back off, which is what keeps the app from reaching for the
        network at all.

  npm install / npm run dev
        Not needed. The React UI is prebuilt into
        app\frontend\dist and FastAPI serves it on the same port,
        so there is no second terminal and no Node.js on this
        machine.

  uvicorn app.main:app --reload
        Use run.ps1 instead. The job queue is in-memory, and
        --reload wipes every in-flight job when transformers writes
        into the model cache.


 WHAT IS IN HERE
----------------------------------------------------------------

  app\                       the project, with model weights included
    backend\data\models\       IndicTrans2 x3      (~3.1 GB)
    backend\data\hf_cache\     Whisper medium      (~1.4 GB)
                               NLLB-200 600M       (~2.3 GB)
                               Indic Parler-TTS    (~3.5 GB)
    frontend\dist\             prebuilt UI, real backend (not the mock)
  wheelhouse\                every Python dependency, as .whl
  bin\                       ffmpeg.exe, ffprobe.exe
  installers\                CPython 3.12 + VC++ redistributable
  setup.ps1                  the one setup command
  run.ps1                    the one start command
  verify_offline.py          proves the models load with no network
  MANIFEST.txt               exact contents and sizes


 REQUIREMENTS
----------------------------------------------------------------

  Windows 10/11, 64-bit (x64, not ARM)
  ~20 GB free disk
  16 GB RAM recommended (Parler-TTS dubbing is the hungry one)
  CPU only -- no GPU, no CUDA, no NVIDIA driver needed

Python 3.12 SPECIFICALLY. Not 3.11, not 3.13, not 3.14. Every wheel
in wheelhouse\ is built for cp312/win_amd64 and pip will reject all
of them on any other version. setup.ps1 installs the right one from
installers\ if it is not already present -- but if this machine
already has 3.13 or 3.14, that is fine and will simply be ignored.


 IF SOMETHING GOES WRONG
----------------------------------------------------------------

"...cannot be loaded because running scripts is disabled"
    PowerShell's execution policy. Use the exact commands above --
    the -ExecutionPolicy Bypass applies to that one command only and
    changes nothing on the machine.

"Could not find a version that satisfies the requirement ..."
    pip is on the wrong Python. Check:
        app\backend\.venv\Scripts\python.exe --version
    It must say 3.12.x. If not, delete app\backend\.venv and re-run
    setup.ps1 -Force.

"DLL load failed while importing ..." on torch or onnxruntime
    Missing VC++ runtime. Run installers\vc_redist.x64.exe by hand,
    then re-run setup.ps1.

Video jobs fail, everything else works
    ffmpeg is not being found. Confirm bin\ffmpeg.exe exists and was
    copied into app\backend\.venv\Scripts\ by setup.ps1.

A model file is reported as "only 52 bytes"
    The transfer flattened Hugging Face's symlinks into stubs. The
    bundle is damaged -- re-copy it as a folder (robocopy), or use
    7-Zip rather than a tool that stores links.

Port 8000 already in use
    powershell -ExecutionPolicy Bypass -File run.ps1 -Port 8080

To re-check the install at any time:
    app\backend\.venv\Scripts\python.exe verify_offline.py --full


 SPEED EXPECTATIONS
----------------------------------------------------------------

CPU-only, and the first job of each kind pays a one-time model load
from disk. On an 8-core machine, transcription runs at roughly
0.67x realtime with Whisper medium -- about 90 seconds of processing
per 60 seconds of audio. That is expected, not a fault.
