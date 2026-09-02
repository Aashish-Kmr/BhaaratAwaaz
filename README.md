# BAIF Bhasha

One app for translating video, audio, and documents between English, Hindi,
and Marathi (any pair), running entirely on one machine.

- `backend/` — FastAPI app: a single-worker job queue, the REST API the
  frontend talks to, and thin adapters that drive the three original
  pipelines. It contains no translation/ASR/TTS logic of its own.
- `backend/vendor/` — the three original projects, vendored so they can
  run in one process. Each keeps its own models, tuning and logic; only
  their `import` lines were rewritten (their top-level module names —
  `config`, `api`, `app`, `services`, `utils` — collided with each
  other), their directories were pointed at `backend/data`, and small
  optional progress/cancellation hooks were added:
  - `vendor/docs_baif/` ← `BAIF-main` — documents (IndicTrans2, pivots
    hi↔mr through English)
  - `vendor/audio_ba/` ← `BhaaratAwaaz-main` — audio (faster-whisper
    **medium** + IndicTrans2 + Parler-TTS dubbing)
  - `vendor/video_baif/` ← `BAIF-Video-main` — video (faster-whisper
    **medium** + **NLLB-200** + ffmpeg subtitle burn-in)
- `frontend/` — React/Vite UI: upload, job queue, subtitle/segment editor.
  Built to static files and served by the backend on the same port — no
  Node.js needed at runtime, only at build time.
- `fonts/` — Devanagari font used by the PDF translation handler.
- `BAIF-main/`, `BhaaratAwaaz-main/`, `BAIF-Video-main/` — the original
  standalone projects, kept as the upstream reference. The runtime uses
  the vendored copies under `backend/vendor/`, not these.

Everything runs on **CPU only** — there is no GPU code path and no device
toggle. The three pipelines each pin themselves to CPU, which was already
their upstream default.

See `PACKAGING.md` for turning this into a distributable executable, or
`packaging/offline/README.md` for shipping the project itself — models,
dependencies and all — to another Windows machine that has no internet.

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
  segments, exportable as SRT/VTT/plain text from the editor, plus an
  on-demand **burned-in subtitle MP4** (rendered from the editor after you
  have reviewed the subtitles, so corrections make it into the video).
  Video jobs do not produce a dubbed track; dubbing is audio-only.

## CPU only

There is no GPU code path, no device toggle, and no CUDA build. Each
vendored pipeline pins itself to CPU, which was already its upstream
default.

Note that a GPU would not make transcription *more accurate* — the same
model with the same decoding settings produces the same text either way.
A GPU is faster, which is only indirectly an accuracy story: it makes a
larger model affordable.

## Tuning speed vs. quality

There are no app-level tuning env vars: each pipeline is a vendored
upstream project that owns its own model choices and decoding settings,
and they deliberately differ. Change them in the pipeline you actually
mean:

| pipeline | file | notable settings |
|---|---|---|
| documents | `vendor/docs_baif/config.py`, `translator.py` | IndicTrans2 model paths, `max_new_tokens` |
| audio | `vendor/audio_ba/shared/config.py` | `ASR_MODEL` (medium), `ASR_BEAM_SIZE`, VAD |
| video | `vendor/video_baif/services/transcriber.py` | `MODEL_SIZE` (medium), beam size, VAD, batch size |

**Whisper model size is the main quality lever.** Measured on this
machine (8 cores, CPU) against a 60 s Marathi clip using the video
pipeline's settings:

| model | 60 s of audio | speed |
|---|---|---|
| `small` | 34.7 s | 1.73× realtime |
| `medium` | 89.3 s | 0.67× realtime |

So `medium` is ~2.6× slower but noticeably better on Indic audio — which
is why both pipelines now use it. Dropping video back to `small` roughly
triples throughput at a real accuracy cost, and would require adding
`small` back to `scripts/download_models.py`.

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
