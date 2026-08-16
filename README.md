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

```bash
# Terminal 1 - backend
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py      # one-time; see PACKAGING.md for options
uvicorn app.main:app --reload

# Terminal 2 - frontend (talks to the backend above via the Vite proxy)
cd frontend
npm install
VITE_USE_MOCK=false npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`).

## Run as one process (what gets packaged)

```bash
cd frontend && npm install && VITE_USE_MOCK=false npm run build && cd ..
cd backend && source .venv/bin/activate && python run.py
```

FastAPI now serves both the API (`/api/*`) and the built UI (`/`) on
`http://127.0.0.1:8000`, and opens it in your browser automatically.

## Supported languages and formats

- Languages: English, Hindi, Marathi — any source paired with either of the
  other two targets.
- Documents: `.docx`, `.pptx`, `.xlsx`, `.csv`, `.pdf` (formatting preserved;
  PDF translation uses the bundled Devanagari font).
- Audio: `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg`, `.flac` — transcript +
  translated segments in the editor, plus an optional AI-dubbed audio track
  once it finishes generating in the background.
- Video: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm` — transcript + translated
  segments, exportable as SRT/VTT/plain text from the editor.

## Known limitations

- The job **queue** is in-memory; it doesn't survive a backend restart
  (uploaded files and translated documents on disk do). Fine for a
  single-machine demo; would need a persisted job table for anything longer
  lived.
- Video translation intentionally does not produce a dubbed audio track
  (subtitles only) — see `backend/app/pipelines/video.py`.
- `ffmpeg` must be on `PATH` for video audio extraction (the only pipeline
  still using an external ffmpeg binary — audio and translation are pure
  Python).
