# BAIF Bhasha — frontend

Offline console for converting video, audio and documents between English,
Hindi and Marathi (any source, any target) — subtitles/segments for video and
audio, translated files for documents. Everything runs on one machine (i5 /
16 GB, no internet). In production this bundle isn't served standalone — the
FastAPI backend serves it directly from `dist/` on the same port, so the
whole app is one process.

## Run it

```bash
npm install          # needs internet ONCE, on a connected machine
npm run dev          # http://localhost:5173 — starts with mock data
```

It boots against an in-memory fake backend, so you can click through the whole
flow with no server running. When the real backend exists:

```bash
VITE_USE_MOCK=false npm run dev
VITE_USE_MOCK=false npm run build    # -> dist/, serve from the local backend
```

Dev requests to `/api` and `/media` are proxied to `http://127.0.0.1:8000`.
Change with `VITE_BACKEND_ORIGIN`.

## Screens

**Upload + job queue** — drag-drop multiple files, pick target language, watch
per-job stage and progress. Cancel, retry and delete. The queue polls every
second while work is running and backs off to 8 s when idle.

**Subtitle editor** (video/audio jobs) — media player on the left, segment
list on the right. The list follows playback, clicking a timestamp seeks, and
each row has an editable translation with the source language beside it.
Split and merge segments, see warnings for over-long lines and fast reading
speeds, then export SRT, VTT, a plain transcript, or a bilingual review file
for proof-readers. Audio jobs also get an optional AI-dubbed audio download
once the backend finishes generating it in the background.

**Document jobs** skip the editor — there's no timeline to scrub — and get a
direct "Download" action for the translated file instead, formatting
preserved server-side.

## Layout

```
src/
  api/
    index.js         # the only import site — picks mock vs http
    http.js          # real backend (REST + polling, XHR upload progress)
    mock.js          # in-memory fake pipeline; delete when backend lands
    sampleContent.js # demo segments
  components/
    ui.jsx           # buttons, badges, cards, formatters
    UploadPanel.jsx
    JobQueue.jsx
    SubtitleEditor.jsx
  hooks/useJobs.js   # polling job list
  lib/
    constants.js     # languages, statuses, file kinds
    subtitles.js     # timestamp maths, SRT/VTT/TXT export, QC warnings
API_CONTRACT.md      # what the backend team needs to implement
```

## For the backend team

Read `API_CONTRACT.md`. Eleven endpoints, all JSON except the multipart
upload. The three that matter most for a working demo: `POST /api/jobs`,
`GET /api/jobs`, `GET /api/jobs/{id}/segments`.

## Notes

- No CDN, no web fonts, no analytics — the bundle is fully self-contained so it
  works on an air-gapped machine.
- Devanagari gets extra line-height via the `.deva` class. If Noto Sans
  Devanagari is not installed on the target machine, install it locally or drop
  a woff2 into `public/` and add an `@font-face` in `src/index.css`.
- Tailwind v4 is configured through the Vite plugin — there is no
  `tailwind.config.js` and no PostCSS setup; theme tokens live in `src/index.css`.
