# API contract — BAIF Bhasha

The frontend talks to exactly one local backend over REST + polling. No
websockets, no third-party services, no outbound internet.

- Base URL: `/api` (dev server proxies to `http://127.0.0.1:8000`, override with
  `VITE_BACKEND_ORIGIN`).
- All request and response bodies are JSON except the upload, which is
  `multipart/form-data`.
- All text is UTF-8. Devanagari must round-trip unchanged.
- Errors: non-2xx with `{ "message": "human readable", "code": "snake_case" }`.

---

## Objects

### Job

```json
{
  "id": "job_a1b2c3",
  "filename": "sendriya-sheti-part1.mp4",
  "kind": "video",
  "bytes": 84233216,
  "durationSec": 52.0,
  "sourceLang": "mr",
  "targetLang": "hi",
  "status": "translating",
  "progress": 0.62,
  "stage": "Translating",
  "createdAt": "2026-08-14T10:12:03Z",
  "finishedAt": null,
  "error": null,
  "segmentCount": 0,
  "includeDubbing": false,
  "dubbedAudioReady": false,
  "burnInStatus": "idle",
  "burnInError": null
}
```

| field | type | notes |
|---|---|---|
| `id` | string | opaque, stable |
| `kind` | `video` \| `audio` \| `document` | derived from the file |
| `durationSec` | number \| null | null until known (always null for documents) |
| `sourceLang` / `targetLang` | `en` \| `hi` \| `mr`, source != target | ISO 639-1, any of the three in either slot |
| `status` | see below | **one of the fixed set** |
| `progress` | 0..1 | overall, not per-stage |
| `stage` | string | free text shown verbatim in the UI |
| `error` | string \| null | set only when `status = "failed"` |
| `segmentCount` | int | 0 until `done`; always 0 for documents |
| `includeDubbing` | bool | set from `include_dubbing` at upload time; audio jobs only, ignored for documents and video |
| `dubbedAudioReady` | bool | audio jobs — true once the AI-dubbed track exists. Dubbing is a pipeline stage, so this is already true when `status = "done"`; when `includeDubbing` was false the stage is skipped entirely and this stays false |
| `burnInStatus` | `idle` \| `rendering` \| `ready` \| `failed` | video jobs — state of the **on-demand** subtitle burn-in, which is independent of `status` and only starts when `POST /burn-in` is called |
| `burnInError` | string \| null | set only when `burnInStatus = "failed"` |

**status values** — the UI switches on these exactly:

```
queued → extracting → transcribing → translating → [dubbing] → done
any    → failed | cancelled
```

Document jobs skip `transcribing`. `dubbing` only occurs for audio jobs
uploaded with `include_dubbing=true`, and the job stays in it until the
dubbed track exists — a job never reports `done` with dubbing still
pending. Video jobs never enter `dubbing`; their extra output (the
burned-in MP4) is requested separately via `POST /burn-in` and tracked by
`burnInStatus`, not `status`.

### Segment

```json
{
  "id": "job_a1b2c3_s0",
  "start": 0.0,
  "end": 4.2,
  "source": "नमस्कार, आज आपण सेंद्रिय शेतीविषयी माहिती घेणार आहोत.",
  "target": "नमस्कार, आज हम जैविक खेती के बारे में जानकारी लेंगे।",
  "confidence": 0.81,
  "edited": false
}
```

`start`/`end` are seconds (float). `source` is Marathi, `target` is the
translation. `confidence` is optional (0..1); anything below 0.75 gets flagged
in the editor. `edited` is set by the frontend when a human changed the text —
the backend should persist it, not compute it.

---

## Endpoints

### `GET /api/status`

```json
{
  "online": true,
  "offlineMode": true,
  "models": [
    { "name": "faster-whisper medium (audio)", "task": "asr", "loaded": true, "sizeMb": null }
  ],
  "queueLength": 1,
  "diskFreeGb": 41.6,
  "ramTotalGb": null,
  "cpuOnly": true
}
```

Polled every 20 s. Must be cheap — no model calls. `loaded` reports
whichever models the three pipelines have lazily loaded so far, so it is
expected to be `false` for everything on a freshly-started server.

`cpuOnly` is always true: this build has no GPU code path and no device
switch.

### `GET /api/jobs`

`{ "jobs": [Job, ...] }` (a bare array is also accepted). Newest first.

Polled every 1 s while any job is non-terminal, every 8 s otherwise.

### `POST /api/jobs`

`multipart/form-data`:

| part | value |
|---|---|
| `file` | the binary |
| `source_lang` | `en` \| `hi` \| `mr` |
| `target_lang` | `en` \| `hi` \| `mr`, must differ from `source_lang` |
| `include_dubbing` | `"true"` \| `"false"`, optional, default `"false"` — audio/video only, ignored for documents |

Returns `201` with the created `Job` (status `queued`). Must respond as soon as
the bytes are on disk — do **not** block until processing finishes.

### `GET /api/jobs/{id}` → `Job`

### `POST /api/jobs/{id}/cancel` → `Job`

Stops the worker if it holds this job, otherwise removes it from the queue.
Idempotent.

### `POST /api/jobs/{id}/retry` → `Job`

Re-queues a `failed` or `cancelled` job using the already-uploaded bytes.

### `DELETE /api/jobs/{id}` → `204`

Deletes the job, its media and its segments.

### `GET /api/jobs/{id}/segments`

`{ "segments": [Segment, ...] }` ordered by `start`. `200` with an empty array
if the job is not done yet.

### `PUT /api/jobs/{id}/segments`

Body: `{ "segments": [Segment, ...] }` — the **full** list, replacing what is
stored. Segments may have been split, merged or reordered, and new ones carry
frontend-generated ids.

Returns `{ "saved": 10, "savedAt": "2026-08-14T10:40:11Z" }`.

### `GET /api/jobs/{id}/media`

Streams the original file with `Accept-Ranges: bytes` and correct
`Content-Type`. Range support is required or scrubbing in the editor breaks.

### `GET /api/jobs/{id}/download`

Document jobs only. Streams the translated file (formatting preserved) with
`Content-Disposition: attachment`. `404` until `status = "done"`.

### `GET /api/jobs/{id}/dubbed-audio`

Audio jobs, only if the job opted in with `include_dubbing=true`. Streams
the AI-dubbed WAV track. `404` until `dubbedAudioReady = true`. Dubbing is
part of the job (the job does not reach `done` until it finishes), so
`dubbedAudioReady` is true by the time `status = "done"`.

### `POST /api/jobs/{id}/burn-in` → `Job`

Video jobs only. Starts an ffmpeg re-encode that burns the job's **current
saved subtitles** into the video, and returns immediately — poll
`burnInStatus` (`idle` → `rendering` → `ready` | `failed`) for progress.

This is deliberately not part of the job pipeline: it is expensive and is
meant to run *after* the transcript has been reviewed and corrected in the
editor, so save segment edits (`PUT /segments`) before calling it. Calling
it again re-renders with whatever is saved at that moment.

`400` if the job is not a video (`not_a_video`) or has not finished
(`not_ready`); `409` (`already_rendering`) if a render is in flight.

### `GET /api/jobs/{id}/burned-in-video`

Streams the burned-in MP4 as an attachment. `404` (`not_ready`) until
`burnInStatus = "ready"`.

---

## Notes for the backend

- **One worker.** The box is an i5 with 16 GB and the models are large; run a
  single job at a time and let the rest sit in `queued`. The UI already shows a
  queue position via `stage`.
- **Progress must move.** Report `progress` at least every couple of seconds
  during transcription, even if it is an estimate from audio position. A frozen
  bar is the main thing that makes a demo look broken.
- **Segment ids must be stable** across `GET`/`PUT` so unsaved edits are not
  lost when the list refreshes.
- Keep `stage` short — it is rendered inside a badge (~24 characters).

## Switching the frontend off the mock

```bash
VITE_USE_MOCK=false npm run dev          # dev, proxied to 127.0.0.1:8000
VITE_USE_MOCK=false npm run build        # static bundle for the offline box
```

`src/api/mock.js` and `src/api/sampleContent.js` can be deleted once the real
backend is in place; nothing outside `src/api/` imports them.
