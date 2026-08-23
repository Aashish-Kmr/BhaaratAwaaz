# BAIF Bhasha

One app for translating video, audio, and documents between English, Hindi,
and Marathi (any pair), running entirely on one machine.

- `backend/` — FastAPI app: document translation (IndicTrans2), audio
  ASR→translate→dub (faster-whisper + IndicTrans2 + Parler-TTS), video
  extract→transcribe→translate (ffmpeg + faster-whisper + IndicTrans2), a
  single-worker job queue, and the REST API the frontend talks to.
- `frontend/` — React/Vite UI: upload, job queue, subtitle/segment editor.
  Built to static files and served by the backend on the same port — no
  Node.js needed at runtime, only at build time.
- `fonts/` — Devanagari font used by the PDF translation handler.
- `BAIF-main/`, `BhaaratAwaaz-main/`, `BAIF-Video-main/` — the original
  standalone projects this app was consolidated from. Left in place as
  reference; not used at runtime.

See `PACKAGING.md` for turning this into a distributable executable.

## Run in development

Two processes, hot-reloading independently:

**macOS / Linux:**

```bash
# Terminal 1 - backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-cpu.txt    # or requirements-gpu.txt, see PACKAGING.md
python scripts/download_models.py      # one-time; see PACKAGING.md for options
uvicorn app.main:app --reload --reload-dir app

# Terminal 2 - frontend (talks to the backend above via the Vite proxy)
cd frontend
npm install
VITE_USE_MOCK=false npm run dev
```

**Windows (PowerShell):**

```powershell
# Terminal 1 - backend
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-cpu.txt    # or requirements-gpu.txt, see PACKAGING.md
python scripts\download_models.py      # one-time; see PACKAGING.md for options
uvicorn app.main:app --reload --reload-dir app

# Terminal 2 - frontend (talks to the backend above via the Vite proxy)
cd frontend
npm install
$env:VITE_USE_MOCK="false"; npm run dev
```

If `.venv\Scripts\Activate.ps1` is blocked by PowerShell's execution policy,
run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first (this
only affects the current terminal session, not the whole machine).

Open the URL Vite prints (default `http://localhost:5173`).

**Do not run bare `uvicorn app.main:app --reload`** (without `--reload-dir
app`) — without it, uvicorn watches the whole `backend/` tree by default,
including `data/hf_cache/`, where `transformers` writes out IndicTrans2's
custom model code the first time it loads. Those writes look like a source
change, trigger a reload, and since the job queue is in-memory, wipe every
in-flight job. `run.py` (used for the packaged single-process app below)
doesn't use `--reload` at all, so it isn't affected.

## Run as one process (what gets packaged)

**macOS / Linux:**

```bash
cd frontend && npm install && VITE_USE_MOCK=false npm run build && cd ..
cd backend && source .venv/bin/activate && python run.py
```

**Windows (PowerShell):**

```powershell
cd frontend; npm install; $env:VITE_USE_MOCK="false"; npm run build; cd ..
cd backend; .venv\Scripts\Activate.ps1; python run.py
```

FastAPI now serves both the API (`/api/*`) and the built UI (`/`) on
`http://127.0.0.1:8000`, and opens it in your browser automatically.

See `PACKAGING.md` for building this into a standalone Windows `.exe` and
installer — the target machine for this app is Windows-only, so that's the
primary packaging path.

## Supported languages and formats

- Languages: English, Hindi, Marathi — any source paired with either of the
  other two targets.
- Documents: `.docx`, `.pptx`, `.xlsx`, `.csv`, `.pdf` (formatting preserved;
  PDF translation uses the bundled Devanagari font).
- Audio: `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac` — transcript +
  translated segments in the editor, plus an opt-in AI-dubbed audio track
  (enable "Include dubbing" at upload time) once it finishes generating in
  the background.
- Video: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm` — transcript + translated
  segments, exportable as SRT/VTT/plain text from the editor, plus the same
  opt-in AI-dubbed audio track as audio jobs (a separate downloadable track,
  not a re-muxed dubbed video).

## GPU acceleration

ASR, translation and TTS default to CPU. If the machine has a CUDA-capable
GPU and a matching CUDA build of `torch`/`ctranslate2` installed, toggle
"Process on GPU" in the UI (or `POST /api/settings/device`) to switch all
three over. This is an app-wide setting, not per-job — flipping it drops any
already-loaded models so they reload on the new device next time they're
used, which briefly slows down whichever job runs right after a switch.

On a low-VRAM GPU, running all three models on GPU at once can be tight —
watch `nvidia-smi` during a job if you hit instability, and consider a
smaller `BAIF_ASR_MODEL` (e.g. `small`) to leave more headroom.

## Tuning speed vs. quality

Audio and video transcripts run through the same ASR and translation code,
so these apply equally to both. All are env vars, unset = the defaults
below:

| var | default | effect of lowering it |
|---|---|---|
| `BAIF_ASR_MODEL` | `medium` | smaller Whisper model (`small`, `base`, `tiny`) — much faster transcription, somewhat less accurate |
| `BAIF_ASR_BEAM_SIZE` | `5` | faster transcription per segment |
| `BAIF_TRANSLATION_NUM_BEAMS` | `5` | faster translation generation per batch |
| `BAIF_TRANSLATION_BATCH_SIZE` | `8` | segments translated per model call — raising it (not lowering) trades memory for fewer, more efficient calls |
| `BAIF_ASR_CPU_THREADS` | `0` (library auto) | CPU threads faster-whisper uses per transcription |
| `BAIF_TORCH_THREADS` | unset (library auto) | CPU threads PyTorch uses for translation |

Translation segments are already batched (multiple segments per
`model.generate()` call, not one call each) — this alone is roughly a 3-4x
speedup over translating one segment at a time on a typical transcript.

**On multi-core CPUs, more threads is not automatically faster.** Benchmarked
on a 10-core Apple Silicon Mac, forcing `BAIF_ASR_CPU_THREADS=10` or
`BAIF_TORCH_THREADS=10` was the same or slightly *slower* than leaving both
on their library defaults (which land around 4 threads on their own) —
Apple's performance/efficiency core split means naively maxing thread count
can hurt. Whether this holds on a different machine (e.g. a uniform-core
Windows/Linux laptop) isn't something to assume either way — benchmark on
the actual demo machine before changing these from their defaults.

## Known limitations

- The job **queue** is in-memory; it doesn't survive a backend restart
  (uploaded files and translated documents on disk do). Fine for a
  single-machine demo; would need a persisted job table for anything longer
  lived.
- Video translation's dubbed audio track is opt-in and, like audio jobs, is a
  separate downloadable WAV — not a video with its audio track replaced. See
  `backend/app/pipelines/video.py` and `backend/app/pipelines/common.py`.
- `ffmpeg` must be on `PATH` for video audio extraction (the only pipeline
  still using an external ffmpeg binary — audio and translation are pure
  Python).
