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

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate     # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

`parler_tts` installs from GitHub (its own setup.py pulls in
`descript-audiotools` from git too) — this step needs `git` and network
access once. Don't also add `descript-audiotools` as its own line in
`requirements.txt`: pip treats a separately-pinned direct-URL requirement for
the same package as a conflicting specifier even when it would resolve to
the same commit, and the install fails.

If you don't need the audio-dubbing bonus feature and want a smaller/faster
install, drop the `parler_tts` and `descript-audio-codec` lines — the rest of
the app (documents, video subtitles, audio transcript+translation) works
fine without them; only `POST /api/jobs/{id}/dubbed-audio` becomes
unreachable.

## 3. Download the models (do this once, early)

```bash
python scripts/download_models.py
```

This fetches, into `backend/data/`:
1. Three IndicTrans2 checkpoints (~600 MB combined) — required for all
   translation (documents, audio, video).
2. The faster-whisper ASR model (~1.5 GB for the `medium` default; set
   `BAIF_ASR_MODEL=small` or `base` before running for a smaller/faster
   model — worth doing if you're tight on time or on modest hardware).
3. Indic Parler-TTS (several GB) — only needed for the audio-dubbing bonus;
   pass `--skip-tts` to leave it out and save real time/bandwidth.

**Four of these five repos are gated on Hugging Face** (everything except
faster-whisper) and this is the one step that needs a human, not just a
script:
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

Output lands in `backend/dist/baif-bhasha/`. This bundles whatever's already
in `backend/data/models` and `backend/data/hf_cache` at build time (see step
3) directly into the app, so the built folder runs fully offline on another
machine with no download or Hugging Face login needed there. Copy the whole
`backend/dist/baif-bhasha/` folder to the target machine and run the
`baif-bhasha` (or `baif-bhasha.exe`) launcher inside it.

`ffmpeg` is not bundled by the spec file — copy an `ffmpeg` binary for the
target OS into the built folder (or ensure it's already on `PATH` there); the
video pipeline shells out to it for audio extraction.

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
