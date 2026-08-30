from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app import config
from app.errors import api_error
from app.jobs import job_store as store
from app.jobs import worker
from app.jobs.models import Job, Segment, now_iso
from app.jobs.store import JobNotFound
from app.pipelines.document import MEDIA_TYPES as DOCUMENT_MEDIA_TYPES
from app.status import model_status

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


def _status_dict() -> dict:
    disk_free_gb = round(shutil.disk_usage(config.DATA_DIR).free / (1024**3), 1)

    queue_length = sum(
        1 for job in store.list() if job.status not in ("done", "failed", "cancelled")
    )

    return {
        "online": True,
        "offlineMode": True,
        "models": model_status(),
        "queueLength": queue_length,
        "diskFreeGb": disk_free_gb,
        "ramTotalGb": None,
        # This build runs entirely on CPU -- the vendored pipelines pin
        # themselves to it and there is no device switch to expose.
        "cpuOnly": True,
    }


@router.get("/status")
def get_status():
    return _status_dict()


@router.get("/jobs")
def list_jobs():
    return {"jobs": [job.to_public_dict() for job in store.list()]}


def _get_job_or_404(job_id: str) -> Job:
    try:
        return store.get(job_id)
    except JobNotFound:
        raise api_error(404, "Job not found.", "job_not_found")


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    return _get_job_or_404(job_id).to_public_dict()


@router.post("/jobs", status_code=201)
async def create_job(
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    include_dubbing: bool = Form(False),
):
    source_lang = source_lang.strip().lower()
    target_lang = target_lang.strip().lower()

    if source_lang not in config.SUPPORTED_LANGUAGES:
        raise api_error(400, f"Unsupported source language: {source_lang}", "bad_source_lang")
    if target_lang not in config.SUPPORTED_LANGUAGES:
        raise api_error(400, f"Unsupported target language: {target_lang}", "bad_target_lang")
    if source_lang == target_lang:
        raise api_error(400, "Source and target language must differ.", "same_language")

    if not file.filename:
        raise api_error(400, "Filename is required.", "missing_filename")

    filename = Path(file.filename).name
    kind = config.kind_of(filename)

    if kind is None:
        raise api_error(400, f"Unsupported file type: {filename}", "unsupported_file_type")

    job_id, job_dir = store.new_job_dir()
    suffix = Path(filename).suffix.lower()
    input_path = job_dir / f"input{suffix}"

    size = 0
    try:
        with input_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise api_error(400, "File exceeds the 2 GB limit.", "file_too_large")
                out.write(chunk)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    job = Job(
        id=job_id,
        filename=filename,
        kind=kind,
        bytes=size,
        source_lang=source_lang,
        target_lang=target_lang,
        include_dubbing=include_dubbing,
        input_path=str(input_path),
        job_dir=str(job_dir),
    )

    store.add(job)
    worker.enqueue(job_id)

    return job.to_public_dict()


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = _get_job_or_404(job_id)

    if job.status == "queued":
        store.update(job_id, status="cancelled", stage="Cancelled", finished_at=now_iso())
    elif job.status not in ("done", "failed", "cancelled"):
        store.update(job_id, cancel_requested=True)

    return store.get(job_id).to_public_dict()


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str):
    job = _get_job_or_404(job_id)

    if job.status not in ("failed", "cancelled"):
        raise api_error(400, "Only failed or cancelled jobs can be retried.", "not_retryable")

    store.update(
        job_id,
        status="queued",
        stage="Queued",
        progress=0.0,
        error=None,
        cancel_requested=False,
        finished_at=None,
    )
    worker.enqueue(job_id)

    return store.get(job_id).to_public_dict()


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    _get_job_or_404(job_id)
    store.delete(job_id)
    return None


@router.get("/jobs/{job_id}/segments")
def get_segments(job_id: str):
    _get_job_or_404(job_id)
    return {"segments": store.load_segments(job_id)}


@router.put("/jobs/{job_id}/segments")
def put_segments(job_id: str, body: dict):
    _get_job_or_404(job_id)

    segments = [
        Segment(
            id=s["id"],
            start=s["start"],
            end=s["end"],
            source=s.get("source", ""),
            target=s.get("target", ""),
            confidence=s.get("confidence"),
            edited=s.get("edited", False),
        )
        for s in body.get("segments", [])
    ]

    store.save_segments(job_id, segments)

    return {"saved": len(segments), "savedAt": now_iso()}


@router.get("/jobs/{job_id}/media")
def get_media(job_id: str):
    job = _get_job_or_404(job_id)

    if not job.input_file.exists():
        raise api_error(404, "Media not found.", "media_not_found")

    media_type, _ = mimetypes.guess_type(job.filename)

    return FileResponse(
        path=job.input_file,
        media_type=media_type or "application/octet-stream",
        filename=job.filename,
    )


@router.get("/jobs/{job_id}/download")
def download_result(job_id: str):
    job = _get_job_or_404(job_id)

    if job.kind != "document":
        raise api_error(400, "Only document jobs have a translated download.", "not_a_document")

    output_file = job.output_file

    if job.status != "done" or output_file is None or not output_file.exists():
        raise api_error(404, "Translated file not ready yet.", "not_ready")

    suffix = output_file.suffix.lower()
    media_type = DOCUMENT_MEDIA_TYPES.get(suffix, "application/octet-stream")

    return FileResponse(
        path=output_file,
        media_type=media_type,
        filename=output_file.name,
        headers={"Content-Disposition": f'attachment; filename="{output_file.name}"'},
    )


@router.post("/jobs/{job_id}/burn-in")
def start_burn_in(job_id: str):
    """
    Render the job's current subtitles into the video.

    Deliberately separate from the job pipeline: this re-encodes the whole
    video with ffmpeg, so it runs only when asked for, against whatever
    subtitles are saved at that moment (i.e. after the user has reviewed
    and corrected them in the editor).
    """

    job = _get_job_or_404(job_id)

    if job.kind != "video":
        raise api_error(400, "Only video jobs can be burned in.", "not_a_video")

    if job.status != "done":
        raise api_error(400, "The job must finish before burning in subtitles.", "not_ready")

    if job.burn_in_status == "rendering":
        raise api_error(409, "A burn-in render is already running.", "already_rendering")

    store.update(job_id, burn_in_status="rendering", burn_in_error=None)
    worker.enqueue_burn_in(job_id)

    return store.get(job_id).to_public_dict()


@router.get("/jobs/{job_id}/burned-in-video")
def download_burned_in_video(job_id: str):
    job = _get_job_or_404(job_id)

    if job.burn_in_status != "ready" or not job.burned_in_video_file.exists():
        raise api_error(404, "Burned-in video not ready yet.", "not_ready")

    filename = f"subtitled_{Path(job.filename).stem}.mp4"

    return FileResponse(
        path=job.burned_in_video_file,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/jobs/{job_id}/dubbed-audio")
def download_dubbed_audio(job_id: str):
    job = _get_job_or_404(job_id)

    if job.kind not in ("audio", "video"):
        raise api_error(400, "Only audio and video jobs produce dubbed audio.", "not_dubbable")

    if not job.dubbed_audio_ready or not job.dubbed_audio_file.exists():
        raise api_error(404, "Dubbed audio not ready yet.", "not_ready")

    return FileResponse(
        path=job.dubbed_audio_file,
        media_type="audio/wav",
        filename=f"dubbed_{Path(job.filename).stem}.wav",
        headers={"Content-Disposition": f'attachment; filename="dubbed_{Path(job.filename).stem}.wav"'},
    )
